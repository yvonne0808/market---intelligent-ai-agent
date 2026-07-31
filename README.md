# Monthly Report Library

这个仓库集中管理两个相互隔离的医疗行业月报工作流，共享本地 Python
虚拟环境和环境变量，但不共享采集状态或业务数据。

## 项目结构

```text
monthly-report-library/
├── china-wechat-med-phar/     # 中国微信公众号医药与医疗器械报告
├── southeast_asia_medtech/    # 东南亚医疗器械市场监测
├── tests/                     # 仓库结构测试
├── .env                       # 两个工作流共享的本地密钥，不提交到 Git
├── .venv/                     # 共享 Python 虚拟环境
└── requirements.txt           # 共享 Python 依赖
```

## 中国微信公众号报告

配置、采集状态、脚本、数据和报告都位于
[`china-wechat-med-phar/`](china-wechat-med-phar/)。

从仓库根目录运行采集器：

```bash
.venv/bin/python china-wechat-med-phar/scripts/main.py
```

详细使用方法见
[`china-wechat-med-phar/README.md`](china-wechat-med-phar/README.md)。

## 东南亚医疗器械报告

东南亚工作流保持为独立 Python package，数据和状态不会与中国微信工作流混用。

例如，从仓库根目录运行其单元测试：

```bash
PYTHONPATH=. .venv/bin/python -m unittest discover \
  -s southeast_asia_medtech/tests -p 'test_*.py'
```

## 本地服务

WeWe RSS 仍是同级的独立项目：

```text
/Users/yvonne/Desktop/forecasting/wewe-rss-local
```

本次目录整理不会修改 WeWe RSS 数据库、GitHub repository、Git remote 或线上报告地址。
