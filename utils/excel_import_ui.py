"""Custom-archive Excel workflow shared with the existing manual editor."""
from copy import deepcopy
from pathlib import Path
from uuid import uuid4

import streamlit as st
from openpyxl.utils import get_column_letter

from utils.excel_import import ALIASES, read_excel, suggest_mapping, convert_rows, metadata_candidates, apply_metadata_candidate
from utils.custom_jackets import prepare_jacket
from utils.diagnostics import begin_report, capture_exception


@st.dialog('Excel 导入教学', width='large')
def import_tutorial(game_type):
    guide = Path('docs/excel_import_guide.md')
    if guide.is_file():
        st.markdown(guide.read_text(encoding='utf-8'))
    else:
        st.write('首行填写表头，一行填写一条记录。上传 .xlsx 后确认列映射和预览，再导入草稿，点击“提交存档修改”。')
    template = Path('static/import_templates') / f'{game_type}_custom_import.xlsx'
    if template.is_file():
        st.download_button('下载样本 Excel', template.read_bytes(), file_name=template.name,
                           mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')


def render_excel_import(game_type, archive_id):
    context = f'excel_{game_type}_{archive_id}'
    with st.expander('从 Excel 批量导入自定义记录'):
        if st.button('导入教学与样本', key=context+'_help'):
            import_tutorial(game_type)
        uploaded = st.file_uploader('选择 Excel 表格', type=['xlsx'], key=context+'_file')
        if not uploaded:
            return
        data = uploaded.getvalue()
        try:
            table = read_excel(data)
            selected_sheet = st.selectbox('工作表', table.sheet_names,
                                          index=table.sheet_names.index(table.sheet), key=context+'_sheet')
            if selected_sheet != table.sheet:
                table = read_excel(data, selected_sheet)
            mapping, suggestions = suggest_mapping(table.headers, game_type)
            st.caption('每个字段只能对应一列。无法识别的列可忽略；相似表头只提供候选，由您确认。')
            options = [None, *ALIASES]
            for index, header in enumerate(table.headers):
                label = f'{get_column_letter(index+1)} 列：{header or "空表头"}'
                mapping[index] = st.selectbox(label, options,
                    index=options.index(mapping[index]),
                    format_func=lambda field: '忽略此列' if field is None else f'{ALIASES[field][0]} ({field})',
                    key=f'{context}_{selected_sheet}_{index}_{header}',
                    help='候选：' + '、'.join(suggestions[index]) if suggestions[index] else '没有识别到候选字段')
            jacket_root = st.text_input('曲绘根目录（使用相对路径时填写）', key=context+'_jacket_root')
            sort_by_order = st.checkbox('按顺序列排序', key=context+'_order')
            mode = st.radio('导入方式', ['追加到当前草稿', '替换当前草稿'], key=context+'_mode', horizontal=True)
            signature = (data, selected_sheet, list(mapping.items()), jacket_root, sort_by_order)
            preview_key = context+'_preview'
            if st.button('预览导入结果', key=context+'_preview_button'):
                report = begin_report('Excel 自定义导入预览', settings={'game_type': game_type, 'rows': len(table.rows)})
                st.session_state['last_diagnostic_report'] = report.report_id
                records, preview = convert_rows(table, mapping, game_type, jacket_root=jacket_root or None,
                                                sort_by_order=sort_by_order)
                st.session_state[preview_key] = {'signature': signature, 'records': records,
                                                'preview': preview, 'batch': uuid4().hex, 'consumed': False}
            draft = st.session_state.get(preview_key)
            if draft and draft['signature'] == signature:
                st.dataframe(draft['preview'], hide_index=True, width='stretch')
                st.write(f"可导入 {len(draft['records'])} 条；无法导入 {sum(r['状态'] == '无法导入' for r in draft['preview'])} 条。")
                images = [r['_import_jacket_path'] for r in draft['records'] if r.get('_import_jacket_path')]
                if images:
                    st.image([prepare_jacket(p) for p in images[:6]], width=120, caption=[Path(p).name for p in images[:6]])
                if draft['records'] and st.checkbox('查找乐曲元数据补全候选（可选）', key=context+'_candidates'):
                    from utils.DataUtils import load_metadata
                    record_index = st.selectbox('选择待补全记录', range(len(draft['records'])),
                                                format_func=lambda i: draft['records'][i]['chart_data']['song_name'], key=context+'_candidate_record')
                    record = draft['records'][record_index]
                    candidates = metadata_candidates(record, load_metadata(game_type))
                    if candidates:
                        chosen = st.selectbox('选择补全候选', [None, *range(len(candidates))], key=context+'_candidate_choice',
                            format_func=lambda i: '保留自定义值' if i is None else f"{candidates[i]['title']} / {candidates[i]['artist']} / {candidates[i]['difficulty']}")
                        if st.button('仅补全该行缺失的曲师和定数', disabled=chosen is None or draft['consumed'], key=context+'_fill_candidate'):
                            apply_metadata_candidate(record, candidates[chosen])
                            row = next(p for p in draft['preview'] if p['Excel行'] == record['raw_data']['excel_row'])
                            row.update(曲师=record['chart_data']['artist'], 定数=record['chart_data']['difficulty'],
                                       Rating=record['dx_rating' if game_type == 'maimai' else 'chuni_rating'])
                            row['提示'] += '；已按选定候选补全缺失字段，自定义曲名保留'
                            draft['batch'] = uuid4().hex
                            st.rerun()
                    else:
                        st.caption('没有符合曲师、谱面类型与难度的补全候选，继续保留自定义值。')
                warnings = any(r['提示'] for r in draft['preview'])
                accepted = st.checkbox('我已检查预览并接受显示的默认值和跳过项', key=context+'_'+draft['batch']+'_accepted')
                replacing = mode == '替换当前草稿' and bool(st.session_state.get('records'))
                replace_confirmed = st.checkbox('确认替换当前未保存的草稿记录', key=context+'_replace') if replacing else True
                disabled = not draft['records'] or draft['consumed'] or not accepted or not replace_confirmed
                if st.button('导入到当前存档草稿', disabled=disabled, key=context+'_apply'):
                    records = [] if mode == '替换当前草稿' else deepcopy(st.session_state.get('records', []))
                    records.extend(deepcopy(draft['records']))
                    for index, record in enumerate(records):
                        record['order_in_archive'] = index
                    st.session_state['records'] = records
                    st.session_state['_force_refresh_editor'] = True
                    draft['consumed'] = True
                    st.session_state['_excel_switch_manual'] = True
                    st.rerun()
                if draft['consumed']:
                    st.success('记录已导入草稿。点击“提交存档修改”后才保存谱面、成绩和曲绘。')
            elif draft:
                st.info('文件或映射已改变，请重新生成预览。')
        except Exception as exc:
            report = capture_exception(exc, 'Excel 自定义导入')
            st.session_state['last_diagnostic_report'] = report.report_id
            st.error(f'Excel 导入失败：{exc}。诊断编号：{report.report_id}')
