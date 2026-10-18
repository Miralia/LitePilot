# LitePilot

基于 [MoviePilot](https://github.com/jxxghp/MoviePilot) 二次开发的精简分支，砍掉站点、订阅、插件等与自用场景无关的模块，只保留影视自动化链条中最核心的部分。

## 保留的能力

- **媒体识别与刮削**：TMDB 元数据识别，支持自定义识别词、制作组表与流媒体平台表
- **整理入库**：重命名、硬链接/移动、季集归档
- **媒体服务器**：Emby 媒体库刷新与同步删除
- **消息通知**：Telegram
- **内置功能**：下载文件同步、媒体服务器联动删除、媒体库封面生成、媒体信息探测

## 与上游的差异

| 模块 | 状态 |
|---|---|
| 站点、订阅、插件市场 | 已移除 |
| 用户管理 | 仅保留用户名密码登录，账号由 swizzin 同步 |
| 登录方式 | 已移除 PassKey |
| 界面语言 | 仅简体中文 |
| 部署方式 | 原生 systemd + nginx，不提供 Docker |

## 安装使用

源码模式部署，不依赖容器：

```shell
git clone https://github.com/Miralia/LitePilot.git
cd LitePilot
```

初始化、启动与配置见 [docs/cli.md](docs/cli.md)。

## 参与开发

- 文档规则入口：[docs/rules/README.md](docs/rules/README.md)
- 开发环境与本地源码运行：[docs/development-setup.md](docs/development-setup.md)
- 测试说明：[docs/testing.md](docs/testing.md)

## 免责申明

- 本软件仅供学习交流使用，任何人不得将本软件用于商业用途，任何人不得将本软件用于违法犯罪活动，软件对用户行为不知情，一切责任由使用者承担。
- 本软件代码开源，基于开源代码进行修改，人为去除相关限制导致软件被分发、传播并造成责任事件的，需由代码修改发布者承担全部责任。

## 致谢

上游项目 [MoviePilot](https://github.com/jxxghp/MoviePilot) 及其作者、贡献者。
