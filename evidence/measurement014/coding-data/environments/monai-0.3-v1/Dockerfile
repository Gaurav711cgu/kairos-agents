FROM kairos-coding-monai:014-itk-v2
USER root
COPY requirements.lock /opt/checker/monai03-requirements.lock
RUN python -m pip install --no-cache-dir --no-compile --no-deps --only-binary=:all: --require-hashes --index-url https://pypi.org/simple -r /opt/checker/monai03-requirements.lock && python -m pip check
USER 10001:10001
