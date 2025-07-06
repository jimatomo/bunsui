FROM python:3.13-slim-bookworm

ARG USERNAME=vscode
ARG USER_UID=1000
ARG USER_GID=$USER_UID

# Create the user
RUN groupadd --gid $USER_GID $USERNAME \
&& useradd --uid $USER_UID --gid $USER_GID -m $USERNAME \
# install git
&& apt-get update \
&& apt-get install -y  --no-install-recommends git zsh curl unzip \
&& apt-get -y clean \
&& rm -rf /var/lib/apt/lists/*

# Install aws cli
RUN case "$(uname -m)" in \
    x86_64) \
        ARCH_ZIP="awscli-exe-linux-x86_64.zip" ;; \
    aarch64) \
        ARCH_ZIP="awscli-exe-linux-aarch64.zip" ;; \
    *) \
        echo "Unsupported architecture: $(uname -m)" >&2; \
        exit 1 ;; \
    esac && \
    curl "https://awscli.amazonaws.com/${ARCH_ZIP}" -o "awscliv2.zip" \
    && unzip awscliv2.zip \
    && ./aws/install \
    && rm -rf awscliv2.zip aws

# switch user
USER $USERNAME

# Create virtual environment.
RUN pip install --no-cache-dir --upgrade pip setuptools wheel

# Install packages requirements.txt
COPY .devcontainer/requirements.txt /tmp/
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# Install Oh My zsh
RUN sh -c "$(curl -fsSL https://raw.github.com/ohmyzsh/ohmyzsh/master/tools/install.sh)" \
# zsh-completions
&& git clone https://github.com/zsh-users/zsh-completions ${ZSH_CUSTOM:-${ZSH:-~/.oh-my-zsh}/custom}/plugins/zsh-completions \
# zsh-autosuggestions
&& git clone https://github.com/zsh-users/zsh-autosuggestions ${ZSH_CUSTOM:-~/.oh-my-zsh/custom}/plugins/zsh-autosuggestions \
# plugin setting
&& sed -i -e 's/plugins=(git)/plugins=(git zsh-completions zsh-autosuggestions)/g' ~/.zshrc

CMD ["zsh"]