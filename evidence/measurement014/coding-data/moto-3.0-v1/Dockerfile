FROM python@sha256:6ff506466f8b1e981719b468cc0023b8ef000b983cdec0eafe119d01f379e31d
ENV PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 AWS_EC2_METADATA_DISABLED=true
COPY requirements.lock /opt/checker/requirements.lock
COPY wheels /opt/checker/wheels
COPY build-requirements.lock /opt/checker/build-requirements.lock
RUN python -m pip install --no-cache-dir --no-compile --no-index --find-links=/opt/checker/wheels --require-hashes -r /opt/checker/build-requirements.lock
RUN python -m pip install --no-build-isolation --no-cache-dir --no-compile --no-index --find-links=/opt/checker/wheels --require-hashes -r /opt/checker/requirements.lock && python -m pip check
USER 10001:10001
WORKDIR /workspace
