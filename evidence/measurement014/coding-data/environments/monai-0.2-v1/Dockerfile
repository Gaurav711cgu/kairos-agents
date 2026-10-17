FROM python@sha256:6ff506466f8b1e981719b468cc0023b8ef000b983cdec0eafe119d01f379e31d
ENV PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2
COPY requirements.lock /opt/checker/requirements.lock
RUN python -m pip install --no-cache-dir --no-compile --only-binary=:all: --require-hashes --index-url https://pypi.org/simple -r /opt/checker/requirements.lock
USER 10001:10001
WORKDIR /workspace
