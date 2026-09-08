# dsh-shutup

让 DSH web 启动即安静的 profile 插件（bundle）：**免 token + 反转 `--no-open` + 允许 `--host 0.0.0.0`**。

## 行为

| 维度 | 上游默认（0.1.2-rc.1） | 装本插件后 |
|---|---|---|
| 浏览器自动打开 | 默认打开，`--no-open` 关闭 | **默认不打开，`--no-open` 反而打开**（字面反转） |
| token 门禁 | 启动打印 `http://127.0.0.1:PORT/?token=xxx`，`/` 与 `/api` 无 cookie 则 `401` | **回到初版 0.0.1-rc.1 风格**：直接 `http://127.0.0.1:PORT/`，无 token、无 401 |
| `--host` | `0.0.0.0` 直接报错拒绝启动 | **允许**（恢复初版 `--host` 文案与 LAN 示例）；打印 `dsh web: http://127.0.0.1:PORT/ (LAN: http://<本机IP>:PORT/)`，两边都是干净 URL |
| Host 信任墙 | 回环 / `--trusted-host` 外 `403` | **保留**：只放行 401，不动 403（LAN IP 由运行时自动加入信任） |

## 安装

```sh
dsh plugin --profile web add <本仓库路径>\shutup-plugin
dsh --profile web --dump-config   # 确认 "# == dsh-shutup" 层：web-startup 被禁用、
                                  # web-startup-shutup/shutup 已插入、web-runtime 的 openBrowser 取反
```

## 使用

```sh
dsh --profile web                              # 安静启动，直接打开打印的干净 URL
dsh --profile web --no-open                    # 反而弹浏览器（反转语义）
dsh --profile web --host 0.0.0.0 --port 3080   # 局域网可访问，同时打印 LAN 地址
dsh plugin --profile web remove dsh-shutup     # 移除
```

`startup.js` 的依赖（`commander` + `@deepseek-ai/dsh-cmdline`）已在包内
`pnpm install` 好；profile 侧是 `link:` 安装，改包内文件即时生效，无需重装。

## ⚠️ 安全警告

`--host 0.0.0.0` + 无 token = **局域网内任何设备可直接操作你的 harness
（约等于远程代码执行）**。只在可信网络用；公用 Wi-Fi / 有不可信设备时别开。
上游当初禁 `0.0.0.0` 就是这个原因。

## 仓库结构

```
.
├── shutup-plugin/          # 正式 bundle（三件套）
│   ├── package.json        # dsh-shutup，dsh.bundle.patch + exports(. / ./startup)
│   ├── cordis.patch.yml    # 禁用上游 web-startup、反转 openBrowser、注册本包两行
│   ├── index.js            # host 半：connection 服务去 token 化（401→放行，403 保留）
│   ├── startup.js          # 上游 web-startup 的去 0.0.0.0 禁令版，提供相同 webStartup 服务
│   └── README.md           # 包级说明
├── preview-shutup.yml      # 免安装预览 overlay（与包内 patch 同步）
```

实现要点：`0.0.0.0` 禁令写在上游 `web-startup` 插件**代码**里，patch 换不掉一行的
`name`（对不上会被 loader 跳过），所以用正统手法——`disabled: true` 掉上游行，
再插入 `web-startup-shutup` 行提供完全相同的 `webStartup` 服务。

## 版本

- `0.1.0` — 免 token + 反转 `--no-open`
- `0.2.0` — 允许 `--host 0.0.0.0`（startup 替换行），鉴权保持初版风格
