"""A report-v2 branch of the existing BookAnalysis durable job, not a queue."""
from __future__ import annotations

import asyncio

from app.agents.deconstruction_model import preview_max_tokens, report_messages, source_report_messages
from app.agents.llm_runtime import LLMRuntime, LLMRuntimeError
from app.core.model_budget import BudgetLedger, ModelBudgetExceeded, pricing_for_model
from app.core.report_pipeline import (
    ReportDraft, ReportReview, ReportVerification, ReviewAccept, ReviewBlocked,
    ReviewRevise, REVIEW_MAX_TOKENS, VERIFY_MAX_TOKENS,
    apply_revision, object_hash, validate_draft, validate_review,
)
from schemas.analysis_report import AnalysisImport, ReportTaskRequest
from app.core.source_report import (
    SOURCE_REPORT_WIRE, SourceReportDraft, apply_source_revision, check_source_directory,
    prepare_source_draft, report_wire, validate_source_candidate, validate_source_review,
)


class _Stopped(Exception):
    pass


class _Rejected(Exception):
    pass


class _ReportTransport:
    """Observe completion, not error codes or usage, at the real HTTP boundary.

    structured() normalizes even repair-time transport errors to bad JSON.
    A complete HTTP rejection/bad JSON is known; an interrupted HTTP/stream is
    not. No headers, payloads or provider exception text are retained here.
    """
    def __init__(self, transport):
        self.transport = transport
        self.unknown = False

    def __call__(self, *args, **kwargs):
        self.unknown = True
        answer = self.transport(*args, **kwargs)
        self.unknown = False
        return answer


async def run_report_job(runner, project, account):
    from app.core.deconstruction_service import DeconstructionServiceError
    job = runner.load(project, account)
    if not job or job.get("kind") != "report-v2" or job["status"] != "running":
        return

    def update(values, *, before_save=None):
        nonlocal job
        current = runner._update_running(job, values, before_save=before_save)
        if current is None:
            raise _Stopped()
        job = current

    def guard():
        runner._check_ready_source(project, account, job)

    def fail(code, message, *, paused=False, unknown=False):
        with runner._lock(project):
            current = runner.load(project, account)
            if not current or not runner._same_job(current, job):
                return
            if current["status"] == "running" or (current["status"] == "paused" and unknown):
                current.update(status="paused" if paused or current["status"] == "paused" else "failed",
                               error_code=code, message=message, inflight=unknown)
                runner.save(current)

    runtime = None
    transport = None

    def get_runtime():
        nonlocal runtime, transport
        if runtime is None:
            runtime = runner.runtime_factory()
            if isinstance(runtime, LLMRuntime):
                transport = _ReportTransport(runtime._transport)
                # Per-job observer only; old preview/book runtimes and the
                # shared per-HTTP reservation/settlement adapter are unchanged.
                runtime = LLMRuntime(runtime.settings, transport=transport, max_retries=0)
        return runtime

    try:
        if job.get("inflight"):
            fail("report_request_unknown", "上次请求结果尚未确认，费用占用已保留；不会自动重发。", paused=True, unknown=True)
            return
        payload = ReportTaskRequest(expected_source_version_id=job["source_version"],
                                    expected_source_revision=job["source_revision"],
                                    expected_source_hash=job["source_hash"])
        _, material, bank, read_text = runner.service.report_material(project, account, payload)
        source_wire = report_wire(job) == SOURCE_REPORT_WIRE
        entries = check_source_directory(job, bank, read_text) if source_wire else None

        def prepare(data):
            if source_wire:
                return prepare_source_draft(data, entries, bank, read_text, producer=job["model"])
            return validate_draft(data, bank, read_text, producer=job["model"])[0], None

        def validate(data):
            if source_wire:
                return validate_source_candidate(data, entries, bank, read_text, producer=job["model"])
            return validate_draft(data, bank, read_text, producer=job["model"])

        def check_review(data, candidate, *, final=False):
            if source_wire:
                return validate_source_review(data, candidate, entries, bank, read_text, final=final)
            return validate_review(data, candidate, bank, read_text, final=final)

        def revise(review, candidate):
            if source_wire:
                return apply_source_revision(review, candidate, entries, bank, read_text, producer=job["model"])
            return apply_revision(review, candidate, bank, read_text, producer=job["model"])

        async def obtain(stage, key, schema, max_tokens, **context):
            nonlocal job, runtime
            guard()
            if key in job:
                return job[key]
            runtime = get_runtime()
            if not runtime.available:
                raise DeconstructionServiceError("model_unavailable", "拆书模型暂不可用，现有结果已保留。", status_code=503)
            if runtime.model != job["model"]:
                raise DeconstructionServiceError("model_changed", "模型配置已变化，本任务未继续发送请求。", status_code=409)
            if max_tokens is None:
                max_tokens = preview_max_tokens(runtime)
            if source_wire:
                messages = source_report_messages(material, bank, entries, stage=stage,
                                                  diagnostics=job.get("draft_diagnostics"), **context)
            else:
                messages = report_messages(material, bank, stage=stage, **context)
            def begin():
                current = runner.load(project, account)
                if current.get("inflight"):
                    raise _Stopped()
                guard()
            update(dict(stage=stage, inflight=True, message={
                "draft": "正在阅读正文并起草报告", "review": "正在逐章核对报告与原文",
                "verify": "正在复核本轮修订"}[stage]), before_save=begin)
            ledger = BudgetLedger.from_public(job["budget"], pricing=pricing_for_model(job["model"]))
            answer = await runner._call(project, account, job, ledger, runtime, stage="report-" + stage,
                                        messages=messages, response_model=schema,
                                        max_tokens=max_tokens, timeout=1220)
            if answer is None:
                raise _Stopped()
            # Persist a returned response even when the author paused during
            # HTTP. It can be validated on explicit resume without paying again.
            with runner._lock(project):
                current = runner.load(project, account)
                if not current or not runner._same_job(current, job):
                    raise _Stopped()
                current.update({key: answer.data, "inflight": False})
                runner.save(current)
                job = current
            if job["status"] != "running":
                raise _Stopped()
            guard()
            return answer.data

        if job["stage"] == "queued":
            update(dict(stage="draft"), before_save=guard)
        if job["stage"] == "draft":
            # The same factory/cap rule as preview; no larger output allowance.
            raw = await obtain("draft", "draft_response", SourceReportDraft if source_wire else ReportDraft,
                               None)
            draft, diagnostics = prepare(raw)
            values = dict(draft=draft, stage="review", cursor=1)
            if source_wire:
                values["draft_diagnostics"] = diagnostics
            update(values, before_save=guard)
        draft, diagnostics = prepare(job["draft"])
        if source_wire and diagnostics != job["draft_diagnostics"]:
            raise ValueError("草稿诊断与冻结原稿不一致")
        if job["stage"] == "review":
            raw = await obtain("review", "review_response", ReportReview, REVIEW_MAX_TOKENS, draft=draft)
            review = check_review(raw, draft)
            if isinstance(review, ReviewBlocked):
                raise _Rejected()
            if isinstance(review, ReviewRevise):
                update(dict(stage="revise", total=3, cursor=2, message="正在应用有源修订"), before_save=guard)
            else:
                # Accept cannot bypass source/identity/structure validation,
                # including when review ignored a persisted diagnostic.
                validate(draft)
                update(dict(stage="adopt", cursor=2, approved_hash=object_hash(draft),
                            message="核对完成，正在保存报告"), before_save=guard)
        if job["stage"] == "revise":
            review = check_review(job["review_response"], draft)
            revised = revise(review, draft)
            update(dict(revised=revised, stage="verify"), before_save=guard)
        if job["stage"] == "verify":
            revised, _ = validate(job["revised"])
            raw = await obtain("verify", "verification_response", ReportVerification, VERIFY_MAX_TOKENS,
                               draft=revised, original=draft, revision=job["review_response"])
            verification = check_review(raw, revised, final=True)
            if not isinstance(verification, ReviewAccept):
                raise _Rejected()
            update(dict(stage="adopt", cursor=3, approved_hash=object_hash(revised),
                        message="修订复核完成，正在保存报告"), before_save=guard)
        if job["stage"] == "adopt":
            # Revalidate stored review provenance on every recovery, not just
            # the mutable phase marker. A half-report is never imported.
            review = check_review(job["review_response"], draft)
            candidate = draft
            if isinstance(review, ReviewRevise):
                candidate = revise(review, draft)
                if candidate != job.get("revised"):
                    raise ValueError("持久修订与审查不一致")
                verdict = check_review(job["verification_response"], candidate, final=True)
                if not isinstance(verdict, ReviewAccept):
                    raise _Rejected()
            elif not isinstance(review, ReviewAccept):
                raise _Rejected()
            if object_hash(candidate) != job["approved_hash"]:
                raise ValueError("待采用报告哈希不一致")
            _, report = validate(candidate)
            def adopt():
                guard()
                result = runner.service.import_report(project, account, AnalysisImport(**payload.model_dump(), report=report))
                adopted["document_id"] = result["result"]["document_id"]
            adopted = {}
            # Existing import is idempotent by the exact persisted report.
            # Crash after import but before the job save repeats no model call.
            with runner._lock(project):
                current = runner.load(project, account)
                if not current or current["status"] != "running" or not runner._same_job(current, job):
                    raise _Stopped()
                adopt()
                current.update(status="completed", stage="completed", error_code=None, inflight=False,
                               document_id=adopted["document_id"], message="拆书完成，报告已保存到本书")
                runner.save(current)
                job = current
    except _Stopped:
        return
    except asyncio.CancelledError:
        fail("report_request_unknown" if job.get("inflight") else "report_interrupted",
             "任务已中断，阶段与费用已保留。", paused=True, unknown=bool(job.get("inflight")))
        raise
    except ModelBudgetExceeded:
        fail("model_budget_exceeded", "本轮预算不足，现有报告与已完成阶段已保留。", paused=True)
    except TimeoutError:
        fail("report_request_unknown", "请求返回尚未确认，费用占用已保留；不会自动重发。", paused=True, unknown=True)
    except _Rejected:
        fail("report_source_blocked", "原文核对仍有未解决的问题，本次报告未采用；原报告已保留。")
    except DeconstructionServiceError as exc:
        fail(exc.code, exc.message)
    except LLMRuntimeError as exc:
        if transport is not None and transport.unknown:
            fail("report_request_unknown", "请求返回尚未确认，费用占用已保留；不会自动重发。", paused=True, unknown=True)
        else:
            fail(exc.code, "模型未返回可用报告，现有报告与费用记录已保留。")
    except OSError:
        fail("analysis_task_unavailable", "任务或预算暂时无法保存，现有报告已保留。",
             paused=True, unknown=bool(job.get("inflight")))
    except (ValueError, KeyError, TypeError):
        fail("report_evidence_invalid", "报告的来源、身份、修订或结构未通过校验；原报告已保留。")
    except Exception:
        # An unexpected defect is fatal, never an ignorable draft diagnostic
        # or an invitation to repeat a possibly-sent request. No exception text
        # (which can contain source/config data) enters the public job.
        unknown = bool(job.get("inflight"))
        fail("report_request_unknown" if unknown else "report_internal_error",
             "任务遇到内部错误，阶段与现有报告已保留。", paused=unknown, unknown=unknown)
