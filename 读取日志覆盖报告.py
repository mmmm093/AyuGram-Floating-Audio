import argparse
import json
import re
import zipfile

def coverage_report(names, open_member):
    """Summarize only observations present in the immutable export snapshot."""
    first = last = None
    records = invalid = 0
    stages = {}
    merged = {}
    for name in names:
        if not re.fullmatch(r"events(?:\.[0-9]+)*\.jsonl", name):
            continue
        with open_member(name) as stream:
            for line in stream:
                try:
                    event = json.loads(line)
                    if not isinstance(event, dict):
                        raise ValueError()
                except (ValueError, UnicodeError):
                    invalid += 1
                    continue
                records += 1
                stamp = event.get("utc")
                if not isinstance(stamp, str) or not stamp:
                    continue
                first = min(first or stamp, stamp)
                last = max(last or stamp, stamp)
                kind = event.get("kind")
                stage = event.get("stage")
                if kind in ("sample","exception") and type(event.get("suppressed")) is int:
                    label = str(stage or kind)
                    merged[label] = merged.get(label,0) + event["suppressed"]
                if kind in ("layout_wait","cover_picker_result","cover_crop_open","cover_crop_save",
                            "effect_selected","effect_applied","media_observed") or (
                        kind=="sample" and stage in ("wave_frame","wave_callback","progress_render")):
                    label = stage if kind=="sample" else kind
                    # UTC has second precision. Show all outcomes tied at the latest second.
                    previous, outcomes = stages.get(label,("",set()))
                    if stamp >= previous:
                        outcome = str(event.get("result","仅记录回调，后续未知"))
                        if event.get("reason"):
                            outcome += " (" + str(event["reason"]) + ")"
                        if stamp > previous:
                            outcomes = set()
                        outcomes.add(outcome)
                        stages[label] = (stamp,outcomes)
    lines = ["日志覆盖报告（UTC）", "包内最早记录：" + (first or "未知"),
             "包内最晚记录：" + (last or "未知"), "可读记录：%d；无法解析：%d" % (records, invalid),
             "首末之间是否连续、区间外缺失原因：未知。",
             "", "限频记录及已报告的合并次数（未写出的尾段未知）"]
    lines.extend(["%s：%d" % item for item in sorted(merged.items())] or ["未知"])
    lines.extend(["", "各环节最近一次有证据的时间与结果（同秒可能有多次操作）"])
    labels = {"layout_wait":"布局等待","cover_picker_result":"选图结果","cover_crop_open":"打开裁剪",
              "cover_crop_save":"保存裁剪","effect_selected":"选择光效","effect_applied":"应用光效",
              "wave_frame":"水波绘制","wave_callback":"水波回调跳过","progress_render":"进度重绘",
              "media_observed":"播放状态复查"}
    for label, title in labels.items():
        stamp, outcomes = stages.get(label,("",set()))
        lines.append(title + "：" + (stamp+" "+", ".join(sorted(outcomes)) if stamp else "未知"))
    lines.append("位图已更新或请求重绘仅代表插件执行到该步骤。画面呈现时间未知。")
    return "\n".join(lines)+"\n"

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="读取悬浮音频圆盘新旧诊断包的记录覆盖范围")
    parser.add_argument("zip_path", help="诊断 ZIP 路径")
    args = parser.parse_args()
    with zipfile.ZipFile(args.zip_path) as archive:
        print(coverage_report(archive.namelist(), archive.open))
