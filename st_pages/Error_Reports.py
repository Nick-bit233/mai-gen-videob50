"""Manual review/download/submission; never uploads on rerun or startup."""
import json
from pathlib import Path
import shutil

import streamlit as st

from utils.app_version import APP_VERSION
from utils.diagnostics import reports_root, package_report, upload_report, begin_report, capture_exception, execute, ReportUploadConflict

st.title("错误报告与硬件检查")
st.caption(f"版本 {APP_VERSION} · 日志仅在确认提交后上传，也可以直接下载。")
root = reports_root()
reports = sorted((p for p in root.glob("*") if (p / "report.json").is_file()), reverse=True)
if st.button("检查硬件编码"):
    report = begin_report("硬件编码检查")
    from utils import AccelRenderer as renderer
    renderer._hw_encoder_cache = None
    renderer._ffmpeg_version_checked = False
    try:
        renderer.check_ffmpeg_version()
        if nvidia := shutil.which('nvidia-smi'):
            device = execute([nvidia, '--query-gpu=name,driver_version', '--format=csv,noheader'],
                             'GPU型号与驱动版本', timeout=10, check=False)
            report.note('gpu_environment', device.stdout.strip())
        codec, name = renderer.detect_hw_encoder()
        report.note("selected_encoder", {"codec": codec, "name": name})
        st.info(f"检查结果：{name} ({codec})。实际渲染仍需按输出参数验证。")
    except Exception as exc:
        capture_exception(exc, "硬件编码检查")
        st.error(str(exc))
    st.session_state['last_diagnostic_report'] = report.report_id
    reports = sorted((p for p in root.glob("*") if (p / "report.json").is_file()), reverse=True)

startup = Path('logs/startup')
if startup.is_dir() and st.button('收集最近一次启动错误'):
    files = sorted((p for p in startup.iterdir() if p.is_file() and p.suffix in {'.txt', '.json'} and p.stat().st_size),
                   key=lambda p: p.stat().st_mtime, reverse=True)[:3]
    if files:
        report = begin_report('启动错误')
        from utils.diagnostics import redact_text
        for index, file in enumerate(files):
            if file.suffix == '.json':
                report.note('startup_environment', json.loads(file.read_text(encoding='utf-8')))
            else:
                (report.directory / f'exception-{index:04d}.txt').write_text(file.read_text(encoding='utf-8', errors='replace'), encoding='utf-8')
                report.note('startup_log', file.name)
        st.session_state['last_diagnostic_report'] = report.report_id
        reports = sorted((p for p in root.glob('*') if (p / 'report.json').is_file()), reverse=True)

if not reports:
    st.info("还没有诊断报告。报错后返回此页，或先运行硬件编码检查。")
else:
    latest = st.session_state.get('last_diagnostic_report')
    index = next((i for i,p in enumerate(reports) if p.name == latest),0)
    chosen = st.selectbox("选择诊断报告", reports, index=index, format_func=lambda p: p.name)
    manifest = json.loads((chosen / "report.json").read_text(encoding="utf-8"))
    st.write(f"报告编号：{chosen.name}")
    st.write(f"阶段：{manifest['stage']}，编码/命令尝试：{len(manifest['attempts'])}")
    st.dataframe([{k: a.get(k) for k in ('stage', 'status', 'returncode', 'category', 'duration_seconds')} for a in manifest['attempts']])
    package = package_report(chosen)
    st.download_button("下载诊断包", package, file_name=f"{chosen.name}.zip", mime="application/zip")
    with st.expander("提交内容预览"):
        st.write(f"压缩包大小：{len(package) / 1024:.1f} KiB；只包含诊断信息与命令日志。")
        import io
        import zipfile
        with zipfile.ZipFile(io.BytesIO(package)) as archive:
            st.write(archive.namelist())
            st.code(archive.read("report.json").decode("utf-8"), language="json")
    config_path = Path("static/error_report_config.json")
    try:
        config = json.loads(config_path.read_text(encoding="utf-8")) if config_path.exists() else {}
    except (ValueError, OSError):
        config = {}
        st.warning("日志上传配置无法读取，请下载诊断包并检查配置文件。")
    endpoint = config.get("endpoint", "")
    if not endpoint:
        st.info("日志桶尚未配置，当前可以下载本地诊断包。线上地址将在版本收尾时补齐。")
    description = st.text_area("问题描述（可选）", key="report_description")
    confirmed = st.checkbox("我已查看提交内容，确认提交此报告", key=f"report_consent_{chosen.name}")
    submitted_key = f"submitted_{chosen.name}"
    if st.button("确认提交错误报告", disabled=not endpoint or not confirmed or bool(st.session_state.get(submitted_key))):
        frozen_key = f"report_package_{chosen.name}"
        if frozen_key not in st.session_state:
            if description.strip():
                # Include only this explicit user description, not session/config contents.
                import io
                import zipfile
                from utils.diagnostics import redact_text
                stream = io.BytesIO(package)
                with zipfile.ZipFile(stream, "a", zipfile.ZIP_DEFLATED) as archive:
                    archive.writestr("description.txt", redact_text(description.strip()))
                package = stream.getvalue()
            st.session_state[frozen_key] = package
        try:
            result = upload_report(st.session_state[frozen_key], chosen.name, endpoint,
                                   config.get('prefix', 'reports'))
            st.session_state[submitted_key] = result
        except ReportUploadConflict as exc:
            st.warning(str(exc))
        except Exception as exc:
            st.error(str(exc))
    if result := st.session_state.get(submitted_key):
        st.success(f"报告已提交：{result['report_id']}；请求编号：{result['request_id']}")
        st.caption("报告由维护者查看；本地诊断包仍可下载。")
