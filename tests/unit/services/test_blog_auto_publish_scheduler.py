import pytest

from app.services import blog_auto_publish_scheduler


class DummyScheduler:
    def __init__(self, timezone=None):
        self.jobs = []
        self.running = False
        self.start_calls = 0
        self.timezone = timezone

    def add_job(self, func, trigger, **kwargs):
        self.jobs.append({"func": func, "trigger": trigger, "kwargs": kwargs})

    def start(self):
        self.running = True
        self.start_calls += 1


def _trigger_timezone_name(trigger) -> str:
    timezone = getattr(trigger, "timezone", None)
    return getattr(timezone, "key", str(timezone))


@pytest.mark.asyncio
async def test_start_auto_blog_scheduler_is_disabled(monkeypatch):
    monkeypatch.setattr(blog_auto_publish_scheduler.settings, "AUTO_BLOG_ENABLED", False)
    monkeypatch.setattr(blog_auto_publish_scheduler, "_scheduler", None)

    blog_auto_publish_scheduler.start_auto_blog_scheduler(app=None)

    assert blog_auto_publish_scheduler._scheduler is None


@pytest.mark.asyncio
async def test_start_auto_blog_scheduler_registers_daily_job(monkeypatch):
    monkeypatch.setattr(blog_auto_publish_scheduler.settings, "AUTO_BLOG_ENABLED", True)
    monkeypatch.setattr(blog_auto_publish_scheduler.settings, "AUTO_BLOG_CRON", "0 20 * * *")
    monkeypatch.setattr(blog_auto_publish_scheduler.settings, "AUTO_BLOG_TIMEZONE", "Asia/Kolkata")
    monkeypatch.setattr(blog_auto_publish_scheduler, "_scheduler", None)
    monkeypatch.setattr(blog_auto_publish_scheduler, "AsyncIOScheduler", DummyScheduler)

    blog_auto_publish_scheduler.start_auto_blog_scheduler(app=None)

    scheduler = blog_auto_publish_scheduler._scheduler
    assert scheduler is not None
    assert scheduler.start_calls == 1
    assert len(scheduler.jobs) == 1
    job = scheduler.jobs[0]
    assert job["kwargs"]["id"] == "auto_blog_publish"
    assert job["kwargs"]["replace_existing"] is True
    assert job["kwargs"]["max_instances"] == 1
    assert job["kwargs"]["coalesce"] is True
    assert _trigger_timezone_name(job["trigger"]) == "Asia/Kolkata"
    assert "hour='20'" in str(job["trigger"])
    assert "minute='0'" in str(job["trigger"])


@pytest.mark.asyncio
async def test_start_auto_blog_scheduler_is_idempotent(monkeypatch):
    monkeypatch.setattr(blog_auto_publish_scheduler.settings, "AUTO_BLOG_ENABLED", True)
    monkeypatch.setattr(blog_auto_publish_scheduler.settings, "AUTO_BLOG_CRON", "0 20 * * *")
    monkeypatch.setattr(blog_auto_publish_scheduler.settings, "AUTO_BLOG_TIMEZONE", "Asia/Kolkata")
    monkeypatch.setattr(blog_auto_publish_scheduler, "_scheduler", None)
    monkeypatch.setattr(blog_auto_publish_scheduler, "AsyncIOScheduler", DummyScheduler)

    blog_auto_publish_scheduler.start_auto_blog_scheduler(app=None)
    first_scheduler = blog_auto_publish_scheduler._scheduler
    blog_auto_publish_scheduler.start_auto_blog_scheduler(app=None)

    assert blog_auto_publish_scheduler._scheduler is first_scheduler
    assert first_scheduler.start_calls == 1
    assert len(first_scheduler.jobs) == 1
