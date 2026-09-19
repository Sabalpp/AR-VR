// Browser workflow with real API/database; no fake camera or movement is injected.
// npm install --no-save playwright, then PLAYWRIGHT_MODULE=/absolute/path/to/playwright/index.mjs node scripts/browser_smoke.mjs
import fs from 'node:fs/promises';
const {chromium}=await import(process.env.PLAYWRIGHT_MODULE||'playwright');
const origin=process.env.TEST_ORIGIN||'http://127.0.0.1:3000';
const password=process.env.DEMO_PASSWORD;
const output=process.env.EVIDENCE_DIR||'/tmp/arvr-browser-evidence';
await fs.mkdir(output,{recursive:true});
const browser=await chromium.launch();
const errors=[];
async function login(page,email){
  await page.goto(origin);
  await page.getByLabel('Email address').fill(email);
  await page.getByLabel('Password',{exact:true}).fill(password||(email.startsWith('therapist')?'DemoTherapist123!':'DemoPatient123!'));
  await page.getByRole('button',{name:'Sign in',exact:true}).click();
}
try {
  const desktop=await browser.newContext({viewport:{width:1440,height:1000}});
  desktop.setDefaultTimeout(20000);
  const page=await desktop.newPage();
  page.on('pageerror',e=>errors.push(e.message));
  await login(page,'therapist@demo.local');
  await page.getByRole('heading',{name:'Your patients'}).waitFor();
  await page.locator('.patient-row').first().click();
  await page.getByRole('button',{name:'Assign exercise'}).click();
  await page.getByLabel('Repetitions',{exact:true}).fill('7');
  await page.getByRole('button',{name:'Add to patient’s plan'}).click();
  await page.getByRole('dialog').waitFor({state:'hidden'});
  await page.getByText('7 repetitions · Phone or headset').first().waitFor();
  await page.screenshot({path:`${output}/therapist-assignment.png`,fullPage:true});
  const mobile=await browser.newContext({viewport:{width:390,height:844},isMobile:true,hasTouch:true});
  mobile.setDefaultTimeout(20000);
  const phone=await mobile.newPage();
  phone.on('pageerror',e=>errors.push(e.message));
  await login(phone,'patient@demo.local');
  await phone.waitForURL('**/patient');
  await phone.getByText('7 reps',{exact:true}).first().waitFor();
  await phone.screenshot({path:`${output}/patient-plan.png`,fullPage:true});
  await phone.getByRole('button',{name:'Set up my camera'}).first().click();
  await phone.getByRole('button',{name:'Allow camera & begin'}).click();
  await phone.locator('.error').waitFor();
  const cameraError=await phone.locator('.error').innerText();
  if(!/device|permission|camera|denied|notfound/i.test(cameraError)) throw new Error('Unexpected camera setup failure: '+cameraError);
  await phone.screenshot({path:`${output}/camera-unavailable.png`,fullPage:true});
  if(process.env.REVIEW_SESSION_ID){
    await page.goto(`${origin}/dashboard/sessions/${process.env.REVIEW_SESSION_ID}`);
    await page.getByRole('heading',{name:'Session review'}).waitFor();
    await page.getByLabel('Replay time').waitFor();
    await page.getByRole('button',{name:'Play playback'}).click();
    await page.getByRole('button',{name:'Pause playback'}).waitFor();
    await page.screenshot({path:`${output}/session-review.png`,fullPage:true});
  }
  const overflow=await phone.evaluate(()=>document.documentElement.scrollWidth>window.innerWidth);
  if(overflow)throw new Error('Mobile page overflows horizontally');
  if(errors.length)throw new Error(errors.join('\n'));
  console.log(JSON.stringify({desktop_assignment_created:true,mobile_plan_visible:true,mobile_viewport_only:true,real_phone_camera_tested:false,camera_unavailable_handled:cameraError,review_playback_tested:!!process.env.REVIEW_SESSION_ID,page_errors:errors,screenshots:output},null,2));
}finally{await browser.close()}
