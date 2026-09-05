import shutil
from pathlib import Path
from services.quality_service import QualityService

def test_quality_records_lifecycle():
    print("=" * 65)
    print("🧪 TEST: Quality Records Logging, Evaluation & Archival Lifecycle")
    print("=" * 65)

    test_dir = Path("/tmp/test_quality_records")
    if test_dir.exists():
        shutil.rmtree(test_dir)
    test_dir.mkdir(parents=True, exist_ok=True)

    qs = QualityService(data_dir=test_dir)

    class DummyUser:
        id = 998877
        username = "test_fan"
        first_name = "Test"

    user = DummyUser()

    # 1. Log two interactions (one good, one bad)
    rec1_id = qs.log_interaction(
        command="nrl",
        user=user,
        query="what are cobbo's latest stats ?",
        response="Selwyn Cobbo: 21 matches, 12 tries, 2,740 run metres.",
        sources=[{"title": "Dolphins NRL", "url": "https://www.dolphinsnrl.com.au"}]
    )
    assert rec1_id is not None, "Failed to log record 1"

    rec2_id = qs.log_interaction(
        command="ask",
        user=user,
        query="is selwyn cobbo returning to broncos?",
        response="Yes, Selwyn Cobbo will return to the Broncos.",
        sources=[{"title": "Old Article", "url": "https://example.com"}]
    )
    assert rec2_id is not None, "Failed to log record 2"

    # 2. Verify pending records
    pending = qs.get_pending_records()
    assert len(pending) == 2, f"Expected 2 pending records, got {len(pending)}"
    assert pending[0]["id"] == rec1_id
    assert pending[1]["id"] == rec2_id
    print(f"✅ Verified 2 interactions logged to pending.jsonl")

    # 3. Simulate Antigravity/Gemini Review
    evaluations = {
        rec1_id: {
            "verdict": "yes",
            "notes": "Accurate 2026 season stats for Selwyn Cobbo at The Dolphins."
        },
        rec2_id: {
            "verdict": "no",
            "notes": "Inaccurate: Cobbo plays for Dolphins, did not return to Broncos. Match at Suncorp in away sheds was historical."
        }
    }

    report_path = qs.generate_quality_review_report(evaluations, reviewer="Antigravity")
    assert report_path.exists(), "Expected review report to be written"
    report_content = report_path.read_text(encoding="utf-8")
    assert "50.0%" in report_content
    assert "Approval Rate" in report_content
    assert "👍 YES" in report_content
    assert "👎 NO" in report_content
    assert rec1_id in report_content
    assert rec2_id in report_content
    print(f"✅ Verified Gemini review report generated: {report_path.name}")

    # 4. Verify Archival to processed.jsonl
    remaining_pending = qs.get_pending_records()
    assert len(remaining_pending) == 0, f"Expected 0 pending records after archival, got {len(remaining_pending)}"

    processed = qs.get_processed_records()
    assert len(processed) == 2, f"Expected 2 processed records in archive, got {len(processed)}"
    assert processed[0]["status"] == "processed"
    assert processed[0]["quality_verdict"] == "yes"
    assert processed[1]["status"] == "processed"
    assert processed[1]["quality_verdict"] == "no"
    print(f"✅ Verified full archival into processed.jsonl; pending.jsonl cleanly cleared!")

    # Cleanup temp dir
    shutil.rmtree(test_dir)
    print("\n🎉 Quality records lifecycle test completed successfully!\n")

if __name__ == "__main__":
    test_quality_records_lifecycle()
