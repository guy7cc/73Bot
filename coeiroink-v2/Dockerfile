# Use Ubuntu 22.04 as the base to match the user's successful environment
FROM ubuntu:22.04

USER root
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

# Install system dependencies
RUN apt-get update && \
    apt-get install -y \
    git \
    curl \
    wget \
    cmake \
    build-essential \
    libsndfile1 \
    ca-certificates \
    software-properties-common \
    libffi-dev \
    libssl-dev \
    unzip \
    gosu && \
    rm -rf /var/lib/apt/lists/*

# Install Python 3.8 using deadsnakes PPA as it's not native to 22.04
RUN add-apt-repository ppa:deadsnakes/ppa && \
    apt-get update && \
    apt-get install -y python3.8 python3.8-dev python3.8-venv python3.8-distutils && \
    rm -rf /var/lib/apt/lists/*

# Setup python aliases and pip
RUN curl -sS https://bootstrap.pypa.io/pip/3.8/get-pip.py | python3.8 && \
    update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.8 1 && \
    update-alternatives --install /usr/bin/python python /usr/bin/python3.8 1

# Create unprivileged user
RUN useradd -ms /bin/bash user

WORKDIR /opt/voicevox_engine

# --- Download VOICEVOX Core Object ---
RUN mkdir -p /opt/voicevox_core && \
    wget -nv -O /tmp/core.zip "https://github.com/VOICEVOX/voicevox_core/releases/download/0.14.2/voicevox_core-linux-x64-cpu-0.14.2.zip" && \
    unzip /tmp/core.zip -d /tmp/core_extracted && \
    mv /tmp/core_extracted/*/* /opt/voicevox_core/ && \
    rm -rf /tmp/core* && \
    echo "/opt/voicevox_core" > /etc/ld.so.conf.d/voicevox_core.conf && \
    ldconfig

# --- Download ONNX Runtime ---
RUN mkdir -p /opt/onnxruntime && \
    wget -nv -O /tmp/onnx.tgz "https://github.com/microsoft/onnxruntime/releases/download/v1.13.1/onnxruntime-linux-x64-1.13.1.tgz" && \
    tar xf /tmp/onnx.tgz -C /opt/onnxruntime --strip-components=1 && \
    rm -rf /tmp/onnx.tgz && \
    echo "/opt/onnxruntime/lib" > /etc/ld.so.conf.d/onnxruntime.conf && \
    ldconfig

# Clone COEIROINK engine
RUN git clone -b c-1.6.0+v-0.12.3 https://github.com/shirowanisan/voicevox_engine.git /tmp/repo && \
    cp -r /tmp/repo/voicevox_engine /opt/voicevox_engine/voicevox_engine && \
    cp /tmp/repo/run.py /tmp/repo/generate_licenses.py /tmp/repo/presets.yaml /tmp/repo/default.csv /opt/voicevox_engine/ && \
    mkdir -p /opt/voicevox_engine/speaker_info && \
    chown -R user:user /opt/voicevox_engine

# Install the exact Python dependencies from the user into the local user environment
COPY requirements-custom.txt /tmp/requirements-custom.txt

RUN gosu user python -m pip install --user --upgrade pip==24.0 setuptools==69.5.1 wheel==0.43.0 && \
    gosu user python -m pip install --user Cython==0.29.24 numpy==1.23.5 && \
    gosu user python -m pip install --user --no-build-isolation -r /tmp/requirements-custom.txt && \
    gosu user python -c "import os; p = os.path.expanduser('~/.local/lib/python3.8/site-packages/pyopenjtalk/version.py'); os.makedirs(os.path.dirname(p), exist_ok=True); open(p, 'w').write('__version__ = \"0.1.6\"\n')" && \
    rm -rf /tmp/repo /tmp/requirements-custom.txt

# Manually generate licenses (optional step, but good for completeness)
# RUN cd /opt/voicevox_engine && gosu user /home/user/.local/bin/python3 generate_licenses.py || true

USER user
ENV PATH="/home/user/.local/bin:${PATH}"

CMD [ "python", "./run.py", "--voicelib_dir", "/opt/voicevox_core/", "--runtime_dir", "/opt/onnxruntime/lib", "--host", "0.0.0.0" ]
