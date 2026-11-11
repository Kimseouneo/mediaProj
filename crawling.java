// console에서 allow pasting 입력 후 진행
(async function () {
  // NOL(야놀자) 티켓 리뷰 수집기 — nol.yanolja.com/ticket/products/...
  // 사용법: 콘솔에 'allow pasting' 입력 후 붙여넣기 → Enter
  const STORAGE_KEY = 'nolReviews';
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const DATE_RE = /\d{4}\.\d{2}\.\d{2}/;

  // 1) 리뷰 전체보기 창 열기 (이미 열려 있으면 건너뜀)
  const findBox = () =>
    [...document.querySelectorAll('*')].find(e =>
      /(auto|scroll)/.test(getComputedStyle(e).overflowY) &&
      e.scrollHeight > e.clientHeight + 50 &&
      e.querySelector('li p'));

  let box = findBox();
  if (!box) {
    const openBtn = [...document.querySelectorAll('button, a')]
      .find(b => /리뷰\s*\d+개\s*전체보기/.test(b.innerText || ''));
    if (!openBtn) {
      console.warn('"리뷰 N개 전체보기" 버튼을 찾지 못했습니다. 리뷰 탭까지 스크롤한 뒤 다시 실행하세요.');
      return;
    }
    openBtn.click();
    await sleep(2000);
    box = findBox();
  }
  if (!box) {
    console.warn('리뷰 스크롤 영역을 찾지 못했습니다.');
    return;
  }

  const getItems = () =>
    [...box.querySelectorAll('li')].filter(li =>
      li.querySelector('p') && DATE_RE.test(li.innerText || ''));

  // 2) 끝까지 스크롤해서 전부 로드 (무한 스크롤)
  let last = -1, same = 0;
  for (let i = 0; i < 100 && same < 3; i++) {
    box.scrollTop = box.scrollHeight;
    await sleep(1000);
    const n = getItems().length;
    same = n === last ? same + 1 : 0;
    last = n;
  }

  // 3) "...더보기" 전부 펼치기
  box.querySelectorAll('p button').forEach(b => {
    if (/더보기/.test(b.innerText)) b.click();
  });
  await sleep(800);

  // 4) 수집
  const collected = getItems().map(li => {
    const p = li.querySelector('p').cloneNode(true);
    p.querySelectorAll('button').forEach(b => b.remove());
    const text = p.innerText.replace(/\s+/g, ' ').trim();
    const name = ((li.querySelector('span') || {}).innerText || '').trim();
    const date = (li.innerText.match(DATE_RE) || [''])[0];

    // 좋아요 버튼: 0이면 "좋아요" 글자, 1 이상이면 숫자가 표시됨
    const likeBtn = [...li.querySelectorAll('button')]
      .find(b => b.querySelector('span') && /^(좋아요|\d+)$/.test(b.innerText.trim()));
    const lt = likeBtn ? likeBtn.innerText.trim() : '';
    const empathy = /^\d+$/.test(lt) ? lt : '0';

    return { name, text, rating: '', empathy, date };
  }).filter(r => r.text);

  // 5) localStorage 누적 저장 + 중복 제거
  let all = [];
  try { all = JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]'); } catch (e) { all = []; }
  const keyOf = r => `${r.name}|||${r.date}|||${r.text}`;
  const seen = new Set(all.map(keyOf));
  collected.forEach(r => {
    const k = keyOf(r);
    if (!seen.has(k)) { seen.add(k); all.push(r); }
  });
  localStorage.setItem(STORAGE_KEY, JSON.stringify(all));

  console.log(`이번 페이지에서 ${collected.length}개 수집, 총 ${all.length}개가 localStorage(${STORAGE_KEY})에 저장되었습니다.`);
})();
