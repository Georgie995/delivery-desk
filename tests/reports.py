"""Builds small synthetic manifest-doctor reports for the tests. No real deliveries."""


def make_report(findings=None, causes=None, tree="D:/Incoming/show-a-ep01", manifests=("set1.md5",)):
    if findings is None:
        findings = [finding("HASH_MISMATCH", "ShowA/Reel01/clip_0004.mov"),
                    finding("HASH_MISMATCH", "ShowA/Reel01/clip_0007.mov")]
    if causes is None:
        causes = [{"code": "CAUSE_DUPLICATE_LISTING", "severity": "ERROR",
                   "summary": "1 path is listed more than once in a manifest with different checksums.",
                   "paths": ["ShowA/Reel01/clip_0004.mov"], "note": "Probable cause, not a verdict."}]
    counts = {s: sum(1 for f in findings if f["severity"] == s) for s in ("ERROR", "WARNING", "INFO")}
    return {
        "header": {"tool": "manifest-doctor", "version": "0.1.0", "run_at": "2026-10-11T14:02:10+01:00",
                   "tree": tree, "result": "PROBLEMS FOUND", "exit_code": 1, "counts": counts,
                   "manifests": [{"path": m, "format": "md5sum", "entries": 5, "stripped_prefix": None}
                                 for m in manifests],
                   "cross_set": None},
        "causes": causes,
        "findings": findings,
    }


def finding(code, path, severity="ERROR"):
    return {"code": code, "severity": severity, "path": path, "detail": "", "manifest": "set1.md5", "line": 1,
            "expected_hash": None, "actual_hash": None, "size": None, "proposed_name": None}


def triage_record(status="FALLBACK", summary="One file failed its checksum check.", reason="no API key"):
    return {"status": status, "draft": {"summary": summary, "result": "PROBLEMS FOUND", "findings": [],
                                        "next_checks": [], "unknowns": []},
            "fallback_reason": reason if status == "FALLBACK" else None, "model": "claude-haiku-5-5",
            "prompt_version": "1"}
