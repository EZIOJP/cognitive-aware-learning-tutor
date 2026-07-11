"""
Huey consumer for LLM probe jobs.

  python -m backend.core.llm_jobs_worker

Requires huey installed (see backend/requirements.txt). Queue DB: data/huey.db
"""

from __future__ import annotations

import sys


def main() -> int:
    from huey.consumer_options import ConsumerConfig
    from huey.consumer import Consumer

    from backend.core.llm_jobs import huey

    config = ConsumerConfig(workers=1, worker_type="thread")
    config.validate()
    consumer = Consumer(huey, **config.values)
    consumer.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
