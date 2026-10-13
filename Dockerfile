# Cloud Run 用。読み込みは Cloud Run に割り当てたサービスアカウントで行う（鍵ファイル不要）
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV PORT=8080
CMD streamlit run app.py --server.port=$PORT --server.address=0.0.0.0
