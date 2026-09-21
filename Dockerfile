FROM python:3.12-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY pitch_engine ./pitch_engine
COPY run_pipeline.py synthetic_generator.py config.json config.docker.json ./

# The synthetic feed is written next to the code on first run.
RUN useradd --create-home app && chown -R app /app
USER app

CMD ["python", "run_pipeline.py", "--config", "config.docker.json"]
