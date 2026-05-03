# 修复记录

用于记录项目开发过程中遇到的 BUG、报错原因、修复方式和验证结果。

## 2026-05-02

### Planner JSON mode 报错

**现象**

调用 `POST /novel/chapters/plan` 时，Planner LLM 调用失败并降级到本地剧情节点。

报错核心信息：

```text
'messages' must contain the word 'json' in some form, to use 'response_format' of type 'json_object'
```

**原因**

`planner_llm.with_structured_output(PlannerOutput)` 底层会启用 JSON 结构化输出。当前 OpenAI 兼容模型服务要求 messages 中必须显式包含 `json` 这个词，否则直接拒绝请求。

**修复**

在 `app/agents/planner_chain.py` 的 system prompt 中明确加入 JSON 输出要求：

```text
输出必须是符合 JSON schema 的结构化 JSON 数据...
不要输出 Markdown，不要输出解释性文字，只返回 JSON。
```

**验证**

重新编译 `planner_chain.py` 通过。

### Planner 返回字段名不符合 Pydantic Schema

**现象**

Planner LLM 已经成功返回内容，但解析 `PlannerOutput` 失败。

报错核心信息：

```text
plot_beats
  Field required
chapter
  Extra inputs are not permitted
nodes
  Extra inputs are not permitted
```

**原因**

代码要求 LLM 返回：

```json
{
  "plot_beats": []
}
```

但模型实际返回：

```json
{
  "chapter": 1,
  "nodes": []
}
```

由于 `PlannerOutput` 使用 `extra="forbid"`，多余字段 `chapter`、`nodes` 会被拒绝，同时必需字段 `plot_beats` 缺失。

**修复**

在 `app/agents/planner_chain.py` 中补充明确 JSON 示例，要求顶层字段必须使用 `plot_beats`，不要使用 `nodes`。

在 `app/models/planner.py` 中新增兼容逻辑：

- `nodes` 自动映射为 `plot_beats`
- 自动丢弃 `chapter`、`chapter_number`
- 节点缺少 `order` 时按列表顺序补齐
- 节点使用 `title`、`event`、`description`、`content` 时尝试映射为 `summary`

**验证**

使用本地模拟数据验证 `chapter + nodes` 可以正常解析为 `PlannerOutput.plot_beats`。

编译检查通过：

```bash
python -m compileall app\models\planner.py app\agents\planner_chain.py
```
