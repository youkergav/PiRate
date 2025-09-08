FROM debian:bookworm

RUN apt-get update && \
    apt-get install --no-install-recommends -y build-essential curl git ca-certificates \
    sudo gpg gpg-agent zip dosfstools rsync genimage mtools mmdebstrap bdebstrap \
    podman crudini zstd pv uidmap python-is-python3 dbus-user-session btrfs-progs \
    dctrl-tools uuid-runtime fdisk python3-pip pipx \
    && rm -rf /var/lib/apt/lists/*

RUN curl -fsSL https://archive.raspberrypi.com/debian/raspberrypi.gpg.key \
    | gpg --dearmor >/usr/share/keyrings/raspberrypi-archive-keyring.gpg \
    && chmod 644 /usr/share/keyrings/raspberrypi-archive-keyring.gpg

ARG RPIIG_GIT_SHA=e5766aa9b2f5a6a09b241c5553833aaa3d4ac4c3
RUN git clone --filter=blob:none --no-checkout https://github.com/raspberrypi/rpi-image-gen.git /opt/rpi-image-gen \
    && git -C /opt/rpi-image-gen fetch --depth=1 origin ${RPIIG_GIT_SHA} \
    && git -C /opt/rpi-image-gen checkout ${RPIIG_GIT_SHA}

ARG USERNAME=imagegen
ENV USER=${USERNAME}
RUN useradd -u 4000 -ms /bin/bash "${USERNAME}" \
    && mkdir -p /home/${USERNAME}/build/work \
    && chown -R ${USERNAME}:${USERNAME} /home/${USERNAME} /opt/rpi-image-gen

ENV DEBIAN_FRONTEND=noninteractive \
    DEBCONF_NONINTERACTIVE_SEEN=true \
    LC_ALL=C.UTF-8 \
    LANG=C.UTF-8

USER ${USERNAME}
WORKDIR /opt/rpi-image-gen

ENV PATH="/home/${USERNAME}/.local/bin:${PATH}"
RUN pipx install poetry && poetry --version
RUN poetry config virtualenvs.create false