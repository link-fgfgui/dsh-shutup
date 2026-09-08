# dsh-shutup

启动即安静的 DSH web 插件：**免 token + 反转 `--no-open` + 允许 `--host 0.0.0.0`**。

## 行为

| 维度 | 上游默认（0.1.2-rc.1） | 装本插件后 |
|---|---|---|
| 浏览器自动打开 | 默认打开，`--no-open` 关闭 | **默认不打开，`--no-open` 反而打开**（字面反转） |
| token 门禁 | 启动打印 `http://127.0.0.1:PORT/?token=xxx`，`/` 与 `/api` 无 cookie 则 `401` | **回到初版 0.0.1-rc.1 风格**：直接 `http://127.0.0.1:PORT/`，无 token、无 401 |
| `--host` | `0.0.0.0` 直接报错拒绝启动 | **允许**（恢复 0.0.1-rc.1 的 `--host` 文案与 LAN 示例）；启动打印 `dsh web: http://127.0.0.1:PORT/ (LAN: http://<本机IP>:PORT/)`，两边都是干净 URL |
| Host 信任墙 | 回环/`--trusted-host` 外 `403` | **保留**：只放行 401，不动 403（LAN IP 由运行时自动加入信任） |

实现要点：`0.0.0.0` 的禁令写在上游 `web-startup` 插件代码里，patch 换不了它的
`name`（会触发 name-mismatch 跳过），所以本包用正统手法——`disabled: true`
掉上游行，再插入 `web-startup-shutup` 行（`startup.js`，与上游逐行一致，仅删
禁令、恢复初版 `--host` 文案），提供完全相同的 `webStartup` 服务。鉴权行为
与 v0.1.0 初版插件一致，未动。

## 安装（正式 bundle，进 profile）

```sh
dsh plugin --profile web add C:\Users\link\Documents\dsh\shutupdsh\shutup-plugin
dsh --profile web --dump-config   # 确认出现 "# == dsh-shutup" 层：web-startup 被禁用、web-startup-shutup/shutup 已插入、web-runtime 的 openBrowser 取反
dsh --profile web                 # 默认不再弹浏览器，直接打开打印的干净 URL
dsh --profile web --no-open       # 反而会弹浏览器（反转语义）
dsh --profile web --host 0.0.0.0 --port 3080   # 局域网可访问，打印 LAN 地址
```

`startup.js` 用到 `commander` + `@deepseek-ai/dsh-cmdline`，已在包内
`pnpm install` 好（`shutup-plugin/node_modules`），profile 侧是 `link:` 安装，
改文件即时生效，无需重装。

## 预览（不安装）

```sh
dsh --profile web --patch ./preview-shutup.yml --dump-config
dsh --profile web --patch ./preview-shutup.yml
```

见根目录 `preview-shutup.yml`（与包内 `cordis.patch.yml` 同步）。

## ⚠️ 安全警告

`--host 0.0.0.0` + 无 token = **局域网内任何人可直接操作你的 harness
（约等于远程代码执行）**。只在可信网络用；公用 Wi-Fi / 有不可信设备时别开。
上游当初禁 `0.0.0.0` 就是这个原因。

## 移除

```sh
dsh plugin --profile web remove dsh-shutup
```

## 已知

- 反转后 `--no-open` 触发自动打开时，终端仍会打印上游原文案
  `opening the default browser; pass --no-open to disable`，文案未改、行为已反转。
- 只覆盖 `web` profile 验证过；其它挂 `dsh-web-app` 的 profile 理论通用。
