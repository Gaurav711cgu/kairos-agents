FROM kairos-coding-moto:014-30-v1
USER 0
COPY requirements.lock /opt/checker/batch-requirements.lock
COPY wheels /opt/checker/batch-wheels
RUN python -m pip install --no-index --no-deps --no-cache-dir --no-compile --find-links=/opt/checker/batch-wheels --require-hashes -r /opt/checker/batch-requirements.lock && python -m pip check
USER 10001:10001
WORKDIR /workspace
