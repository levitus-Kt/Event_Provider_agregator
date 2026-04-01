FROM python:3.11-slim


RUN addgroup --system --gid 1000 appuser && \
    adduser --system --uid 1000 --ingroup appuser appuser

WORKDIR /

COPY requirements.txt .
RUN pip install -r requirements.txt
COPY --chown=appuser:appuser . .

USER appuser

ENV PYTHONPATH=.
CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000", "--app-dir", "."]