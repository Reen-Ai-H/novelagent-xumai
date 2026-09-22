# 叙脉公开拆书案例

这是《魔道祖师（[重生]未删）》126 章拆解的只读展示包，包含全书导读、剧情地图、人物卡、双时间线和矛盾/疑问汇总。

## 本地预览

在项目根目录运行：

```powershell
.venv\Scripts\python.exe -m http.server 3090 --directory public_case
```

然后打开 <http://127.0.0.1:3090/>。

## 命令行部署（另一台电脑无需网页登录）

本目录已经附带 `cloudbaserc.json` 和 `Deploy-CloudBase.cmd`。在另一台 Windows 电脑上安装 Node.js 18+ 后，打开 PowerShell 或命令提示符，首次只需执行一次：

```powershell
.\Deploy-CloudBase.cmd -Login
```

CLI 会在终端中要求输入腾讯云 `SecretId` 和 `SecretKey`，不会打开网页登录，也不会把密钥写入项目。登录态保存在该电脑的用户配置中。之后每次更新页面只需执行：

如果不想在另一台电脑输入长期密钥，可以改用设备码方式：运行 `.\Deploy-CloudBase.cmd -DeviceLogin`，再把终端显示的链接和用户码交给当前已登录腾讯云的浏览器完成一次授权。授权后同样无需再次网页登录。

```powershell
.\Deploy-CloudBase.cmd -Force
```

查看当前线上版本可以执行 `.\Deploy-CloudBase.cmd -Info`。脚本使用 CloudBase CLI 的 `tcb app deploy`，会把本目录的纯静态文件部署到现有的 `xumai-public-case` 应用根路径 `/`。

如果只想先检查命令而不部署，可以运行 `npx --yes --package=@cloudbase/cli tcb app deploy --help`。没有 Node.js 时，脚本会直接提示安装，不会改动项目文件。

### 密钥建议

不要把 `SecretId`、`SecretKey` 写入 `cloudbaserc.json`、脚本或 Git。建议在腾讯云创建专用子账号，只授予 CloudBase 所需权限，并在不用时删除或轮换密钥。腾讯云 API 密钥是账号级凭证，丢失后影响范围较大；如接受一次设备码授权，也可以改用 `tcb login` 的设备码流程，避免长期保存密钥。

## 手动上传

也可以把本目录中的 `index.html`、`styles.css`、`app.js`、`data.json`、`robots.txt` 和本说明上传到腾讯云 CloudBase 静态网站托管的站点根目录。上传后使用控制台提供的默认 HTTPS 域名分享案例。

这个包不包含小说全文，只包含拆解结果和必要的短证据摘录。`data.json` 中后段报告保留了“Codex 补齐/待核对”标识，公开演示时不要把这些标识描述成经过人工逐句认证的结论。

CloudBase 控制台：<https://console.cloud.tencent.com/tcb/hosting>
