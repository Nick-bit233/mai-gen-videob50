// Actual browser file selection and Streamlit round trips in the isolated app.
import fs from 'node:fs/promises';
import path from 'node:path';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';
const require=createRequire(path.join(process.cwd(),'browser-check.cjs'));
const {chromium}=require('playwright');
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const output=path.join(root,'test_output','release128-browser');
await fs.mkdir(output,{recursive:true});
const browser=await chromium.launch({executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',headless:true});
let page;
try {
  page=await browser.newPage({viewport:{width:1440,height:1000}});
  const errors=[];
  page.on('pageerror',error=>errors.push(error.message));
  await page.goto('http://127.0.0.1:18528/custom');
  await page.getByRole('button',{name:'确定用户名',exact:true}).waitFor();
  const username='browser-128-'+Date.now();
  await page.getByRole('textbox',{name:'您还没有设置用户名，请自拟一个用户名以创建存档',exact:true}).fill(username);
  await page.getByRole('button',{name:'确定用户名',exact:true}).click();
  await page.getByRole('button',{name:'新建空白存档',exact:true}).click();
  await page.getByText('从 Excel 批量导入自定义记录',{exact:true}).click();
  await page.locator('input[type=file]').first().setInputFiles(path.join(root,'static/import_templates/maimai_custom_import.xlsx'));
  await page.getByRole('button',{name:'预览导入结果',exact:true}).click();
  // Streamlit's styled checkbox hides the native input; click its visible label.
  await page.getByText('我已检查预览并接受显示的默认值和跳过项',{exact:true}).click();
  await page.getByRole('button',{name:'导入到当前存档草稿',exact:true}).click();
  await page.getByText('记录已导入草稿。点击“提交存档修改”后才保存谱面、成绩和曲绘。',{exact:true}).waitFor();
  await page.getByRole('button',{name:'提交存档修改',exact:true}).click();
  await page.getByText('更改已保存到数据库！',{exact:true}).waitFor();
  await page.getByRole('button',{name:'加载此存档进行编辑',exact:true}).click();
  // The existing load action reruns immediately, so its transient success text
  // is not a persistence assertion. Verify the reloaded record choices instead.
  await page.getByTestId('stSelectbox').filter({hasText:'选择记录'}).locator('input').click();
  await page.getByRole('option',{name:'#1 自定义示例一 (Example_1)',exact:true}).waitFor();
  await page.getByRole('option',{name:'#2 自定义示例二 (Example_2)',exact:true}).waitFor();
  await page.keyboard.press('Escape');
  await page.screenshot({path:path.join(output,'excel-import.png'),fullPage:true});
  const body=await page.locator('body').innerText();
  if (errors.length || body.includes('Traceback (most recent call last)')) throw new Error(JSON.stringify(errors));
  await fs.writeFile(path.join(output,'verification.json'),JSON.stringify({username,actual_file_picker:true,preview:true,save_reload:true,page_errors:errors},null,2));
  console.log(JSON.stringify({username,actual_file_picker:true,save_reload:true,page_errors:errors}));
} catch(error) {
  if(page) {
    await page.screenshot({path:path.join(output,'failure.png'),fullPage:true});
    await fs.writeFile(path.join(output,'failure.txt'),await page.locator('body').innerText());
    console.log(await page.getByRole('checkbox',{name:'我已检查预览并接受显示的默认值和跳过项',exact:true}).evaluate(e=>({rect:e.getBoundingClientRect().toJSON(),expander:e.closest('details')?.open,display:getComputedStyle(e).display,visibility:getComputedStyle(e).visibility})).catch(()=>null));
  }
  throw error;
} finally {
  await browser.close();
}
