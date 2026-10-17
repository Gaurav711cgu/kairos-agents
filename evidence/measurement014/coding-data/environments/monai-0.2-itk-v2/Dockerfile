FROM kairos-coding-monai:014-v1
USER root
COPY requirements.lock /opt/checker/itk-requirements.lock
RUN python -m pip install --no-cache-dir --no-compile --only-binary=:all: --require-hashes --index-url https://pypi.org/simple -r /opt/checker/itk-requirements.lock
USER 10001:10001
