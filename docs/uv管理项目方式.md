```
# 激活环境
source .venv/bin/activate

# 安装项目
uv pip install [xxx] 

更新requirements.txt

# 阿里镜像源地址
https://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com

# 使用 uv pip install ,使用阿里镜像源安装 agent 依赖组 (已安装)
uv pip install "agentscope[full]" --index-url https://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com
```