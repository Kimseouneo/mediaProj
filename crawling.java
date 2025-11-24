
(function () {
  const STORAGE_KEY = 'interparkReviews';

  // 1. li.bbsItem 요소 모두 가져오기
  const items = document.querySelectorAll('li.bbsItem');

  const collected = [];

  items.forEach(li => {
    // (1) 텍스트: p.bbsText
    const textEl = li.querySelector('p.bbsText');
    let text = textEl ? textEl.innerText : '';
    text = text.replace(/\s+/g, ' ').trim();
    if (!text) return;

    // (2) 평점: li 내부의 data-star 가진 요소
    const starEl = li.querySelector('[data-star]');
    const rating = starEl ? starEl.getAttribute('data-star') : '';

    // (3) 공감 수: .bbsItemInfoList 안에서 "공감"이 들어간 텍스트에서 숫자만 추출
    let empathy = '';
    const infoRoot = li.querySelector('.bbsItemInfoList') || li.closest('li')?.querySelector('.bbsItemInfoList');
    if (infoRoot) {
      // 예: "작성자 ○○ | 2025.11.01 | 공감 3" 같은 전체 텍스트에서
      const txt = infoRoot.innerText.replace(/\s+/g, ' ');
      const m = txt.match(/공감[^0-9]*([0-9]+)/);
      if (m) {
        empathy = m[1]; // "3"
      }
    }

    collected.push({ text, rating, empathy });
  });

  // 4. localStorage에 누적 저장 + 중복 제거
  const prevRaw = localStorage.getItem(STORAGE_KEY);
  let all = prevRaw ? JSON.parse(prevRaw) : [];

  const prevSet = new Set(all.map(r => `${r.text}|||${r.rating}|||${r.empathy}`));

  collected.forEach(r => {
    const key = `${r.text}|||${r.rating}|||${r.empathy}`;
    if (!prevSet.has(key)) {
      prevSet.add(key);
      all.push(r);
    }
  });

  localStorage.setItem(STORAGE_KEY, JSON.stringify(all));

  console.log(`이번 페이지에서 ${collected.length}개 수집, 총 ${all.length}개가 localStorage에 저장되었습니다.`);
})();
