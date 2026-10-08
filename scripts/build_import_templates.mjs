// Build the two shipped sample workbooks with the managed Artifact Tool runtime.
import fs from 'node:fs/promises';
import path from 'node:path';
import { createRequire } from 'node:module';
import { pathToFileURL, fileURLToPath } from 'node:url';

const require = createRequire(path.join(process.cwd(), 'artifact-builder.cjs'));
const { Workbook, SpreadsheetFile } = await import(pathToFileURL(require.resolve('@oai/artifact-tool')).href);
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const output = path.join(root, 'outputs', '01a11ab1-7c98-7760-af9d-9c9f120f3105', 'import-templates');
const target = path.join(root, 'static', 'import_templates');
await fs.mkdir(output, {recursive:true});
await fs.mkdir(target, {recursive:true});
const common = ['song_name','artist','song_id','chart_type','level_index','difficulty','achievement','fc_status','fs_status','play_count','clip_title_name','order_in_archive','jacket_path','video_path','video_source','source_pid'];
const explanations = {
  song_name:'曲名，空值将显示未命名谱面。', artist:'曲师，空值使用未知曲师。', song_id:'来源歌曲 ID，作为参考保留；自定义谱面使用独立 ID。',
  chart_type:'舞萌支持 SD 或 DX，中二填写 Normal。', level_index:'BASIC、ADVANCED、EXPERT、MASTER、RE:MASTER 或 ULTIMA。',
  difficulty:'谱面定数，例如 14.5，也可填写 ?。', achievement:'舞萌填写百分比，如 100.5 或 Excel 百分比；中二填写整数分数。',
  fc_status:'FC 状态，支持 none、fc 等游戏选项。', fs_status:'FS 或 Full Chain 状态，支持 none 等游戏选项。',
  play_count:'游玩次数，缺失使用 0。', clip_title_name:'成片中的自定义片段标题。', order_in_archive:'顺序，仅在导入时勾选按此列排序才使用。',
  jacket_path:'本地曲绘路径，使用相对路径时在程序里填写曲绘根目录。', video_path:'可选本地视频路径。',
  video_source:'可选 Bilibili 链接或 BV 号。', source_pid:'分 P 从 1 开始。', max_dx_score:'谱面最大 DX 分数。',
  dx_score:'个人 DX 分数。', dx_rating:'舞萌 Rating，显式填写优先保留，空值按有效成绩和定数计算。',
  chuni_rating:'中二 Rating，显式填写优先保留，空值按有效成绩和定数计算。'
};
for (const game of ['maimai','chunithm']) {
  const wb = Workbook.create();
  const sheet = wb.worksheets.add('Sheet1');
  const guide = wb.worksheets.add('字段说明');
  const fields = [...common, ...(game === 'maimai' ? ['max_dx_score','dx_score','dx_rating'] : ['chuni_rating'])];
  const first = {song_name:'自定义示例一',artist:'示例曲师',song_id:'00001',chart_type:game==='maimai'?'DX':'Normal',level_index:'MASTER',difficulty:14.5,
    achievement:game==='maimai'?1.005:1009000,fc_status:game==='maimai'?'ap':'aj',fs_status:'none',play_count:3,clip_title_name:'Example_1',order_in_archive:1,
    jacket_path:'',video_path:'',video_source:'',source_pid:1,max_dx_score:0,dx_score:0,dx_rating:null,chuni_rating:null};
  const second = {...first,song_name:'自定义示例二',song_id:'00002',difficulty:'?',achievement:0,fc_status:'none',play_count:0,clip_title_name:'Example_2',order_in_archive:2};
  const end = String.fromCharCode(64+fields.length);
  sheet.getRange(`A1:${end}3`).values = [fields,fields.map(f=>first[f]??null),fields.map(f=>second[f]??null)];
  sheet.getRange(`A1:${end}3`).format.font = {name:'Arial',size:11};
  sheet.getRange(`A1:${end}3`).format.columnWidth = 22;
  sheet.getRange(`A1:${end}3`).format.rowHeight = 28;
  sheet.getRange(`A1:${end}1`).format = {fill:'#203A57',font:{name:'Arial',size:11,bold:true,color:'#FFFFFF'},wrapText:true,verticalAlignment:'center'};
  sheet.getRange(`A2:${end}3`).format.fill = '#EEF4FB';
  sheet.getRange('A1:C3').format.columnWidth = 26;
  sheet.getRange('C2:C3').setNumberFormat('@');
  sheet.showGridLines = false;
  sheet.freezePanes.freezeRows(1);
  sheet.freezePanes.freezeColumns(2);
  const achievementCol = String.fromCharCode(65+fields.indexOf('achievement'));
  sheet.getRange(`${achievementCol}2:${achievementCol}3`).setNumberFormat(game==='maimai'?'0.0000%':'0');
  const levelCol = String.fromCharCode(65+fields.indexOf('level_index'));
  sheet.getRange(`${levelCol}2:${levelCol}501`).dataValidation = {rule:{type:'list',values:['BASIC','ADVANCED','EXPERT','MASTER',game==='maimai'?'RE:MASTER':'ULTIMA']}};
  guide.getRange('A2').values = [[game==='maimai'?'舞萌自定义导入字段':'中二自定义导入字段']];
  guide.getRange('A2').format.font = {name:'Arial',size:15,bold:true};
  guide.getRange('A4:B7').values = [
    ['使用方法','删除 Sheet1 样本行后填写记录，首行保留表头。'],
    ['导入流程','上传、确认列映射、查看预览、导入草稿，最后点击提交存档修改。'],
    ['缺失和错误','预览会显示使用的默认值，曲绘缺失时记录仍可导入。'],
    ['示例数据','所有样本曲目和成绩均为演示，不是玩家真实数据。']
  ];
  guide.getRange('A9:B9').values = [['标准字段','说明']];
  guide.getRange(`A10:B${9+fields.length}`).values = fields.map(f=>[f,explanations[f]]);
  guide.getRange(`A4:B${9+fields.length}`).format.font = {name:'Arial',size:11};
  guide.getRange(`A4:B${9+fields.length}`).format.rowHeight = 32;
  guide.getRange(`A4:A${9+fields.length}`).format.columnWidth = 25;
  guide.getRange(`B4:B${9+fields.length}`).format.columnWidth = 100;
  guide.getRange('A9:B9').format = {fill:'#203A57',font:{name:'Arial',size:11,color:'#FFFFFF',bold:true}};
  guide.showGridLines = false;
  wb.recalculate();
  const inspect = await wb.inspect({kind:'table',range:`Sheet1!A1:${end}3`,include:'values,formulas',tableMaxRows:3,tableMaxCols:fields.length,maxChars:1800});
  await fs.writeFile(path.join(output,`${game}-inspection.ndjson`),inspect.ndjson);
  for (const [name,range] of [['data-left','A1:F3'],['data-middle','G1:M3'],['data-right',`N1:${end}3`],['guide',`A1:B${9+fields.length}`]]) {
    const rendered = await wb.render({sheetName:name==='guide'?'字段说明':'Sheet1',range,scale:1.5,format:'png'});
    await fs.writeFile(path.join(output,`${game}-${name}.png`),new Uint8Array(await rendered.arrayBuffer()));
  }
  const xlsx = await SpreadsheetFile.exportXlsx(wb);
  const name = `${game}_custom_import.xlsx`;
  await xlsx.save(path.join(output,name));
  await fs.copyFile(path.join(output,name),path.join(target,name));
  console.log(`${name}: exported and rendered`);
}
