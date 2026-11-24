# Docker 部署与验收

本仓库从 `super-scholar-v3.9.1.zip` 整理了 3.11.0 源码。原压缩包内的 `.git`、虚拟环境、依赖、构建缓存、SQLite 数据库、凭据密钥和用户上传研究材料没有进入公开源码目录或镜像。

在根目录运行：

```powershell
docker compose up -d --build --wait
```

打开 `http://127.0.0.1:3000`，后端健康检查是 `http://127.0.0.1:8000/health`。首次启动自动执行 Alembic 迁移。SQLite 数据与上传材料分别放在 Docker 命名卷 `scholar_data`、`scholar_storage`，容器重建后仍保留。前后端只绑定宿主机的 `127.0.0.1`；不要直接暴露到公网。本应用没有多用户认证，输入真实论文和密钥前应确认运行环境受信任。

AI、OpenAlex、Semantic Scholar 与 Clarivate 等连接需在“系统连接与解析”中按各自许可和账号配置。未配置时，页面和本地材料流程仍可访问，但模型深度理解和外部学术数据完整性不能据此验收。没有项目级 `LICENSE` 时，公开源码可阅读，不代表允许第三方复制修改。

配置模板位于 [`backend/.env.example`](backend/.env.example) 和 [`frontend/.env.example`](frontend/.env.example)。Docker 版的 SQLite 路径、存储卷及前后端连接已经写在 `compose.yaml`，不需要把真实 `.env` 放入仓库。需要外部服务时，优先在页面的“系统连接与解析”保存密钥；源码开发模式才按模板在各自目录创建不受 Git 跟踪的 `.env` / `.env.local`。请勿把真实密钥填入模板文件。

源码启动方式见 [中文说明](README.zh-CN.md)。
