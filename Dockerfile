# briarPipe — run the curator anywhere.
#
#   docker build -t briarpipe .
#   docker run --rm -v "$PWD:/data" -w /data \
#     -e LLM_API_KEY=sk-... briarpipe --store local
#
# Pair with any scheduler (host cron, k8s CronJob, etc.) — run.py decides whether
# an edition is actually due, so a daily tick is plenty.
FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENTRYPOINT ["python", "run.py"]
