(function () {
  const STORAGE_KEY = 'interparkReviews';
  const raw = localStorage.getItem(STORAGE_KEY);

  if (!raw) {
    console.log('저장된 리뷰가 없습니다. 먼저 수집용 스크립트를 실행해 주세요.');
    return;
  }

  const all = JSON.parse(raw);

  // ★ 헤더를 한글로 변경 (순서: 리뷰내용, 평점, 공감)
  const rows = [['리뷰내용', '평점', '공감']];

  all.forEach(r => {
    rows.push([
      r.text || '',      // 리뷰 내용
      r.rating || '',    // 평점
      r.empathy || ''    // 공감 수
    ]);
  });

  function toCsvRow(fields) {
    return fields
      .map(f => {
        const s = String(f).replace(/"/g, '""');
        return `"${s}"`;
      })
      .join(',');
  }

  const csvContent = rows.map(toCsvRow).join('\r\n');

  // 한글 깨짐 방지용 BOM 추가
  const BOM = '\uFEFF';
  const blob = new Blob([BOM + csvContent], {
    type: 'text/csv;charset=utf-8;'
  });

  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'interpark_reviews_merged.csv';
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);

  // 다운로드 후 localStorage 비우기
  localStorage.removeItem(STORAGE_KEY);

  console.log(`총 ${all.length}개의 리뷰를 interpark_reviews_merged.csv 로 저장했고, localStorage에서 데이터는 삭제했습니다.`);
})();
