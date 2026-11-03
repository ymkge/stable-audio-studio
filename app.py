"""Entrypoint for Stable Audio Studio application."""

import sys
from core.config import config
from ui.gradio_app import create_ui


def main():
    print("=" * 60)
    print(" 🎵 Starting Stable Audio Studio (Local Web UI)")
    print(f" - Model ID: {config.model_id}")
    print(f" - Compute Device: {config.device.upper()}")
    print(f" - Output Directory: {config.output_dir}")
    print("=" * 60)

    demo = create_ui()

    try:
        demo.launch(
            inbrowser=True,
            server_name="127.0.0.1",
            server_port=7860,
            show_error=True,
            quiet=False,
        )
    except KeyboardInterrupt:
        print("\nShutdown requested by user (KeyboardInterrupt). Exiting...")
        sys.exit(0)
    except Exception as e:
        print(f"\nServer error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
