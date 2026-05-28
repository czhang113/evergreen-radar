# 资产长青雷达

这是一个把股票观察脚本改成手机可查看网页面板的 Streamlit 项目。

## 本地运行

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run app.py
```

打开终端中显示的本地地址，例如：

```text
http://localhost:8501
```

同一 Wi-Fi 下手机访问电脑局域网 IP 加端口，例如：

```text
http://你的电脑IP:8501
```

## 修改股票池

主要修改 `config.yaml`：

- `user_positions`：你的真实持仓锚点
- `macro`：宏观天气台
- `groups`：ETF、个股、观察名单
- `watch_trigger`：观察名单触发条件

## 部署方案

最省事：

1. 把这几个文件上传到 GitHub 仓库。
2. 登录 Streamlit Community Cloud。
3. 选择仓库。
4. 入口文件填 `app.py`。
5. 部署完成后，把网址收藏到手机浏览器。

更稳定但需要服务器：

1. 准备一台 VPS。
2. 安装 Python。
3. 上传项目。
4. `pip install -r requirements.txt`。
5. `streamlit run app.py --server.address 0.0.0.0 --server.port 8501`。
6. 用 Nginx + HTTPS 反代到自己的域名。
