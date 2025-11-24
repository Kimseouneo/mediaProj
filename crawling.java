(function () {
  const STORAGE_KEY = 'interparkReviews';

  const items = document.querySelectorAll('li.bbsItem');
  const collected = [];

  items.forEach((li, idx) => {
    // 1) 리뷰 텍스트
    const textEl = li.querySelector('p.bbsText');
    let text = textEl ? textEl.innerText : '';
    text = text.replace(/\s+/g, ' ').trim();
    if (!text) return; // 내용 없는 건 스킵

    // 2) 평점
    const rating = getRating(li);

    // 3) 공감 수 (수정된 부분)
    const empathy = getEmpathy(li);

    // 디버깅: 공감 수를 못 찾은 경우 콘솔에 출력
    if (!empathy) {
      console.warn(`[리뷰 ${idx + 1}] 공감 수를 찾지 못했습니다. HTML 구조:`, li.innerHTML.substring(0, 200));
    }

    collected.push({ text, rating, empathy });
  });

  // === 평점 추출 함수 (기존과 동일) ===
  function getRating(root) {
    // (1) data-star
    const starEl = root.querySelector('[data-star]');
    if (starEl) {
      const val = starEl.getAttribute('data-star') || starEl.dataset && starEl.dataset.star;
      if (val) return String(val);
    }

    // (2) aria-label="평점 5점" 등
    const ariaEl = root.querySelector('[aria-label*="점"]');
    if (ariaEl) {
      const label = ariaEl.getAttribute('aria-label') || ariaEl.innerText;
      const m = label && label.match(/([0-9]+(?:\.[0-9]+)?)/);
      if (m) return m[1];
    }

    // (3) ★ 개수
    const starTextRoot = root.querySelector('.bbsStar, .bbsStarArea, .star, .rating');
    if (starTextRoot) {
      const starText = starTextRoot.textContent || '';
      const stars = (starText.match(/★/g) || []).length;
      if (stars > 0) return String(stars);
    }

    return '';
  }

  // === 공감 수 추출 함수 (Interpark용 강화 버전) ===
  function getEmpathy(root) {
    // 1) 다양한 선택자로 공감 버튼/요소 찾기
    const likeSelectors = [
      '.bbsLikeBtn',
      '.bbsItemInfo .bbsLikeBtn',
      '.bbsItemInfoList .bbsLikeBtn',
      'a[class*="Like"]',
      'button[class*="Like"]',
      '.likeBtn',
      '[class*="공감"]',
      'a[title*="공감"]',
      'button[title*="공감"]'
    ];

    for (const selector of likeSelectors) {
      const likeBtn = root.querySelector(selector);
      if (!likeBtn) continue;

      // data 속성들 확인
      const dataAttrs = [
        likeBtn.getAttribute('data-cnt'),
        likeBtn.getAttribute('data-count'),
        likeBtn.getAttribute('data-like'),
        likeBtn.getAttribute('data-empathy'),
        likeBtn.dataset?.cnt,
        likeBtn.dataset?.count,
        likeBtn.dataset?.like,
        likeBtn.dataset?.empathy
      ];

      for (let val of dataAttrs) {
        if (val && String(val).match(/^[0-9]+$/)) {
          return String(val);
        }
      }

      // title, aria-label 확인
      const title = likeBtn.getAttribute('title') || likeBtn.getAttribute('aria-label') || '';
      if (title) {
        const m = title.match(/공감\s*([0-9]+)|([0-9]+)\s*공감|([0-9]+)/);
        if (m) return m[1] || m[2] || m[3];
      }

      // textContent 확인
      const text = likeBtn.textContent || likeBtn.innerText || '';
      const numMatch = text.match(/([0-9]+)/);
      if (numMatch) return numMatch[1];
    }

    // 2) 공감 버튼 옆의 숫자 요소 찾기 (span, em, strong 등)
    const likeBtn = root.querySelector('.bbsLikeBtn, [class*="Like"], [class*="공감"]');
    if (likeBtn) {
      // 형제 요소에서 숫자 찾기
      let sibling = likeBtn.nextElementSibling;
      while (sibling && sibling !== root) {
        const text = sibling.textContent || '';
        const m = text.match(/([0-9]+)/);
        if (m) return m[1];
        sibling = sibling.nextElementSibling;
      }

      // 부모 요소 내에서 숫자 찾기
      const parent = likeBtn.parentElement;
      if (parent) {
        const allText = parent.textContent || '';
        const m = allText.match(/공감\s*([0-9]+)|([0-9]+)\s*공감/);
        if (m) return m[1] || m[2];
      }
    }

    // 3) li.bbsItemInfoList 전체에서 "공감 숫자" 패턴 찾기
    const infoLis = root.querySelectorAll('li.bbsItemInfoList, .bbsItemInfo li');
    for (const li of infoLis) {
      const text = li.textContent || li.innerText || '';
      if (text.includes('공감')) {
        const m = text.match(/공감\s*([0-9]+)|([0-9]+)\s*공감/);
        if (m) return m[1] || m[2];
      }

      // ::before content 확인
      try {
        const style = window.getComputedStyle(li, '::before');
        let content = style?.getPropertyValue('content') || '';
        if (content && content !== 'none' && content !== '""') {
          content = content.replace(/^['"](.*)['"]$/, '$1').trim();
          if (content.includes('공감')) {
            const m = content.match(/공감\s*([0-9]+)|([0-9]+)\s*공감/);
            if (m) return m[1] || m[2];
          }
        }
      } catch (e) {
        // ::before 접근 실패 시 무시
      }
    }

    // 4) 전체 리뷰 항목에서 "공감" 키워드와 숫자 함께 있는 부분 찾기
    const allText = root.textContent || root.innerText || '';
    const empathyMatch = allText.match(/공감\s*([0-9]+)|([0-9]+)\s*공감/);
    if (empathyMatch) {
      return empathyMatch[1] || empathyMatch[2];
    }

    // 5) 마지막 시도: 숫자만 있는 요소 중 공감 버튼 근처의 것
    const numbers = root.querySelectorAll('span, em, strong, b');
    for (const numEl of numbers) {
      const text = numEl.textContent || '';
      if (text.match(/^[0-9]+$/)) {
        const parent = numEl.parentElement;
        if (parent && (parent.textContent || '').includes('공감')) {
          return text;
        }
      }
    }

    // 못 찾으면 빈 문자열 반환
    return '';
  }

  // === localStorage에 누적 저장 + 중복 제거 ===
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
