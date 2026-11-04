# Homebrew formula for CAMR, the memory engine. Written for a tap (Satasdin/homebrew-camr), not tested: Homebrew is
# not installed on the machine it was written on, and no tap exists yet.
# From a clone, today (Homebrew installs formulae only from a tap):
#   brew tap-new $USER/camr
#   cp packaging/homebrew/camr.rb "$(brew --repo $USER/camr)/Formula/"
#   brew install --HEAD $USER/camr/camr
#   brew services start camr                            # camr serve --backend ollama, kept running
class Camr < Formula
  desc "Memory for on-device language models: an OpenAI-compatible endpoint with memory"
  homepage "https://github.com/Satasdin/CAMR"
  license "MIT"
  head "https://github.com/Satasdin/CAMR.git", branch: "camr-build"
  # A release adds its tarball, for `brew install camr` without --HEAD:
  #   url "https://github.com/Satasdin/CAMR/archive/refs/tags/v0.0.1.tar.gz"
  #   sha256 "<shasum -a 256 of that tarball>"

  depends_on arch: :arm64 # the engine runs its models with MLX, on Apple silicon
  depends_on :macos
  depends_on "python@3.12"

  def install
    engine = libexec/"engine"
    system Formula["python@3.12"].opt_bin/"python3.12", "-m", "venv", engine
    system engine/"bin/python", "-m", "pip", "install", "--no-cache-dir", buildpath/"v2"
    bin.install_symlink engine/"bin/camr"
  end

  def caveats
    <<~EOS
      Start the endpoint (in front of Ollama on 127.0.0.1:11434):
        camr serve --backend ollama
      then point any OpenAI client at http://127.0.0.1:11436/v1.
      Memory lives in ~/.camr/default. The models (about 1.3 GB) are downloaded on first use.
    EOS
  end

  service do
    run [opt_bin/"camr", "serve", "--backend", "ollama"]
    keep_alive true
    log_path var/"log/camr.log"
    error_log_path var/"log/camr.log"
  end

  test do
    assert_match "camr ", shell_output("#{bin}/camr version")
    assert_match "OpenAI-compatible", shell_output("#{bin}/camr serve --help")
  end
end
