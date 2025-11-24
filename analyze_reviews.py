import csv
import os
import json
from pathlib import Path
import re
import time
import argparse

# 공감(좋아요) 가중치 설정
# 예: weight = clamp(max(1, likes) ** LIKES_WEIGHT_EXP, 1, LIKES_WEIGHT_MAX)
LIKES_WEIGHT_EXP = 1.2
LIKES_WEIGHT_MAX = 100.0

def analyze_review_for_beginners(csv_file_path):
    """
    CSV 파일을 읽어서 초급자 적합성을 분석합니다.
    
    Args:
        csv_file_path: CSV 파일 경로
        
    Returns:
        dict: 분석 결과 딕셔너리
    """
    reviews = []
    ratings = []
    likes_weights = []  # 공감/좋아요 수 기반 가중치 (없으면 1)
    
    # CSV 파일 읽기
    try:
        with open(csv_file_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            
            # CSV 헤더 확인 및 데이터 읽기
            for row in reader:
                # 리뷰 내용 추출 (다양한 컬럼명 지원)
                review_text = None
                rating = None
                likes = None
                
                for key in row.keys():
                    key_lower = key.lower()
                    if '리뷰' in key_lower or 'review' in key_lower or '내용' in key_lower or 'comment' in key_lower:
                        review_text = row[key]
                    elif '평점' in key_lower or 'rating' in key_lower or '점수' in key_lower or 'score' in key_lower:
                        try:
                            rating = float(row[key])
                        except (ValueError, TypeError):
                            rating = None
                    elif ('공감' in key_lower or '좋아요' in key_lower or '추천수' in key_lower or
                          'helpful' in key_lower or 'like' in key_lower or 'upvote' in key_lower or 'votes' in key_lower):
                        try:
                            likes = float(row[key]) if str(row[key]).strip() != '' else None
                        except (ValueError, TypeError):
                            likes = None
                
                if review_text:
                    reviews.append(review_text)
                    # 공감 가중치: 없으면 1
                    if likes is None:
                        weight = 1.0
                    else:
                        try:
                            raw = float(likes)
                        except Exception:
                            raw = 1.0
                        base = max(1.0, raw)
                        weight = min(LIKES_WEIGHT_MAX, base ** LIKES_WEIGHT_EXP)
                    likes_weights.append(weight)
                if rating is not None:
                    ratings.append(rating)
    except Exception as e:
        return {
            'error': f'CSV 파일 읽기 오류: {str(e)}',
            'suitable': False,
            'confidence': 0
        }
    
    if not reviews and not ratings:
        return {
            'error': 'CSV 파일에서 데이터를 찾을 수 없습니다.',
            'suitable': False,
            'confidence': 0
        }
    
    # 평점 분석
    # 리뷰 수와 가중치 배열 길이가 다를 수 있으므로 방어
    if len(likes_weights) != len(reviews):
        # 불일치 시 모든 가중치를 1로 초기화
        likes_weights = [1.0] * len(reviews)
    # 평점도 리뷰 길이에 맞춰 가중치가 존재하도록 최소 길이로 자름
    min_len_for_ratings = min(len(ratings), len(likes_weights)) if ratings else 0
    if ratings and min_len_for_ratings > 0:
        weights_for_ratings = likes_weights[:min_len_for_ratings]
        ratings_trimmed = ratings[:min_len_for_ratings]
        weight_sum = sum(weights_for_ratings) or 1.0
        avg_rating = sum(r * w for r, w in zip(ratings_trimmed, weights_for_ratings)) / weight_sum
        positive_weight = sum(w for r, w in zip(ratings_trimmed, weights_for_ratings) if r >= 4)
        positive_ratio = (positive_weight / weight_sum) if weight_sum > 0 else 0
    else:
        avg_rating = None
        positive_ratio = 0
    
    # 리뷰 내용 분석 (초급자 관련 키워드)
    beginner_keywords_positive = [
        '초보', '초급', '처음', '입문', '쉽다', '쉬움', '간단', '부담없', 
        '추천', '좋아', '만족', '괜찮', '좋은', '편하다', '무난',
        'beginner', 'easy', 'simple', 'good', 'recommend'
    ]
    
    beginner_keywords_negative = [
        '어렵', '난이도', '복잡', '전문', '고급', '중급', '어려움',
        'difficult', 'hard', 'complex', 'advanced', 'expert'
    ]
    
    positive_count = 0.0
    negative_count = 0.0
    
    for idx, review in enumerate(reviews):
        review_lower = review.lower()
        w = likes_weights[idx] if idx < len(likes_weights) else 1.0
        # 배우명(팬심) 신호 보정: 배우 언급 과다 시 가중치 하향
        # 단순 휴리스틱: '배우' 키워드, 또는 한국어 인명 + '님' 패턴
        if 'actor_bias_inited' not in locals():
            actor_name_pattern = re.compile(r'[가-힣]{2,3}\s*배우|[가-힣]{2,3}\s*님')
            work_signal_keywords = [
                '연출', '구성', '스토리', '대본', '무대', '조명', '음악', '편집', '전개', '메시지',
                '완성도', '연출력', '작품성', '연기력', '호흡', '서사'
            ]
            actor_bias_inited = True
        actor_mentions = review_lower.count('배우') + len(actor_name_pattern.findall(review_lower))
        work_signals = sum(1 for kw in work_signal_keywords if kw in review_lower)
        bias_mult = 1.0
        if actor_mentions >= 2 and work_signals == 0:
            bias_mult = 0.6
        elif actor_mentions >= 1 and work_signals < 2:
            bias_mult = 0.85
        # 최종 가중치 보정 및 적용
        effective_w = max(0.3, min(1.0, bias_mult)) * w
        if idx < len(likes_weights):
            likes_weights[idx] = effective_w
        # 연령대 키워드 집계 준비
        # 기본은 성인으로 판단하되, 언급 카운트가 가장 많은 연령대를 추천
        # 한국어 축약, 학년 표기 등을 폭넓게 포함
        if 'age_counts' not in locals():
            age_groups = {
                '초등학생': [
                    '초등', '초등생', '초등학생', '어린이', '아이', '초1', '초2', '초3', '초4', '초5', '초6'
                ],
                '중학생': [
                    '중등', '중학생', '중1', '중2', '중3'
                ],
                '고등학생': [
                    '고등', '고등생', '고등학생', '고1', '고2', '고3'
                ],
                '성인': [
                    '성인', '어른', '대학생', '직장인'
                ],
            }
            age_counts = {k: 0 for k in age_groups.keys()}
            # 부정 문맥 키워드 (피하/금지/관람불가/부적합/적합하지 등)
            negative_age_context = [
                '피하', '피하세요', '피해주세요', '금지', '관람불가', '부적합', '적합하지',
                '비추', '추천하지', '안됨', '안 돼', '안돼', '불가', '금함', '동반 금지', '동반금지'
            ]
        # 연령 키워드 카운트 (리뷰 한 건에서 여러 그룹 키워드가 있으면 모두 카운트)
        for group, keywords in age_groups.items():
            for kw in keywords:
                start_pos = 0
                while True:
                    found = review_lower.find(kw, start_pos)
                    if found == -1:
                        break
                    left = max(0, found - 12)
                    right = min(len(review_lower), found + len(kw) + 12)
                    context = review_lower[left:right]
                    has_negative_context = any(neg in context for neg in negative_age_context)
                    if has_negative_context and group in ('초등학생', '중학생', '고등학생'):
                        age_counts[group] -= w
                        age_counts['성인'] += w
                    else:
                        age_counts[group] += w
                    start_pos = found + len(kw)
        # 긍정 키워드 체크
        for keyword in beginner_keywords_positive:
            if keyword in review_lower:
                positive_count += w
                break
        # 부정 키워드 체크
        for keyword in beginner_keywords_negative:
            if keyword in review_lower:
                negative_count += w
                break
    
    total_weighted_with_keywords = 0.0
    for idx, r in enumerate(reviews):
        rl = r.lower()
        if any(kw in rl for kw in beginner_keywords_positive + beginner_keywords_negative):
            total_weighted_with_keywords += likes_weights[idx] if idx < len(likes_weights) else 1.0
    keyword_sentiment_ratio = (positive_count - negative_count) / max(total_weighted_with_keywords, 1.0)
    
    # 종합 판단
    scores = []
    
    # 연령대 최다 언급 그룹 계산 (동률인 경우 임의 우선순위: 초등학생 > 중학생 > 고등학생 > 성인)
    recommended_age_group = '성인'
    if 'age_counts' in locals() and any(c > 0 for c in age_counts.values()):
        ordered = sorted(
            age_counts.items(),
            key=lambda x: (x[1], {'초등학생': 4, '중학생': 3, '고등학생': 2, '성인': 1}[x[0]]),
            reverse=True
        )
        recommended_age_group = ordered[0][0]
    else:
        # 명시적 언급이 없다면 성인으로 판단
        age_counts = {k: 0 for k in ['초등학생','중학생','고등학생','성인']}
        recommended_age_group = '성인'
    
    # 평점 기반 점수 (5점 만점 기준, 공감 가중 평균 사용)
    if avg_rating is not None:
        if avg_rating >= 4.5:
            scores.append(1.0)
        elif avg_rating >= 4.0:
            scores.append(0.8)
        elif avg_rating >= 3.5:
            scores.append(0.6)
        elif avg_rating >= 3.0:
            scores.append(0.4)
        else:
            scores.append(0.2)
    
    # 긍정 리뷰 비율 (공감 가중 비율 사용)
    if positive_ratio >= 0.8:
        scores.append(1.0)
    elif positive_ratio >= 0.6:
        scores.append(0.7)
    elif positive_ratio >= 0.4:
        scores.append(0.5)
    else:
        scores.append(0.3)
    
    # 키워드 감성 분석
    if keyword_sentiment_ratio > 0.3:
        scores.append(0.8)
    elif keyword_sentiment_ratio > 0:
        scores.append(0.6)
    elif keyword_sentiment_ratio > -0.3:
        scores.append(0.4)
    else:
        scores.append(0.2)

    # 공감(좋아요) 기반 신뢰 가중 점수: 평균 공감 수에 따라 보너스
    avg_likes = (sum(likes_weights) / len(likes_weights)) if likes_weights else 1.0
    likes_bonus = 0.0
    # 최소 1을 기준, 값이 클수록 보너스. 간단한 구간 가중.
    if avg_likes >= 50:
        likes_bonus = 0.15
    elif avg_likes >= 20:
        likes_bonus = 0.1
    elif avg_likes >= 5:
        likes_bonus = 0.05
    else:
        likes_bonus = 0.0
    # 점수에 보너스 반영 (과도 상승 방지 위해 0.15 한도)
    if likes_bonus > 0:
        scores.append(min(1.0, likes_bonus + 0.5))  # 보수적으로 0.5~1.0 사이로 한 개 요소로 추가
    
    # 최종 점수 계산
    final_score = sum(scores) / len(scores) if scores else 0.5
    suitable = final_score >= 0.6
    confidence = final_score
    
    # 작품명 추출 (파일명에서)
    work_name = Path(csv_file_path).stem
    
    return {
        'work_name': work_name,
        'suitable': suitable,
        'confidence': round(confidence * 100, 1),
        'final_score': round(final_score, 2),
        'avg_rating': round(avg_rating, 2) if avg_rating else None,
        'total_reviews': len(reviews),
        'total_ratings': len(ratings),
        'positive_ratio': round(positive_ratio * 100, 1),
        'keyword_analysis': {
            'positive_keywords_found': round(positive_count, 1),
            'negative_keywords_found': round(negative_count, 1),
            'sentiment_ratio': round(keyword_sentiment_ratio, 2)
        },
        'age_recommendation': {
            'recommended_group': recommended_age_group,
            'counts': {k: (round(v, 1) if isinstance(v, float) else v) for k, v in age_counts.items()}
        },
        'empathy': {
            'used': any(w != 1.0 for w in likes_weights),
            'avg_likes': round(avg_likes, 2) if likes_weights else None,
            'total_likes': round(sum(likes_weights), 1) if likes_weights else None
        },
        'reason': generate_reason(suitable, avg_rating, positive_ratio, keyword_sentiment_ratio)
    }


def generate_reason(suitable, avg_rating, positive_ratio, keyword_sentiment_ratio):
    """판단 근거를 생성합니다."""
    reasons = []
    
    if avg_rating:
        if avg_rating >= 4.5:
            reasons.append(f"평균 평점이 {avg_rating:.2f}점으로 매우 높습니다.")
        elif avg_rating >= 4.0:
            reasons.append(f"평균 평점이 {avg_rating:.2f}점으로 높습니다.")
        elif avg_rating < 3.0:
            reasons.append(f"평균 평점이 {avg_rating:.2f}점으로 낮습니다.")
    
    if positive_ratio >= 0.8:
        reasons.append(f"리뷰의 {positive_ratio*100:.1f}%가 4점 이상입니다.")
    elif positive_ratio < 0.4:
        reasons.append(f"리뷰의 {positive_ratio*100:.1f}%만 4점 이상입니다.")
    
    if keyword_sentiment_ratio > 0.3:
        reasons.append("입문자에게 적합하다는 긍정적인 언급이 많습니다.")
    elif keyword_sentiment_ratio < -0.3:
        reasons.append("난이도가 높거나 전문적이라는 언급이 많습니다.")
    
    if not reasons:
        reasons.append("분석 데이터가 부족하여 판단이 어렵습니다.")
    
    return " ".join(reasons)


def generate_html(results_list):
    """분석 결과를 HTML로 생성합니다."""
    html = """<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>작품 초급자 적합성 분석 결과</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 20px;
            min-height: 100vh;
        }
        
        .container {
            max-width: 1200px;
            margin: 0 auto;
        }
        
        h1 {
            color: white;
            text-align: center;
            margin-bottom: 30px;
            font-size: 2.5em;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
        }
        
        .work-card {
            background: white;
            border-radius: 15px;
            padding: 25px;
            margin-bottom: 20px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
            transition: transform 0.3s ease;
        }
        
        .work-card:hover {
            transform: translateY(-5px);
        }
        
        .work-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
            padding-bottom: 15px;
            border-bottom: 2px solid #f0f0f0;
        }
        
        .work-name {
            font-size: 1.8em;
            font-weight: bold;
            color: #333;
        }
        
        .result-badge {
            padding: 15px 30px;
            border-radius: 25px;
            font-weight: bold;
            font-size: 1.3em;
            box-shadow: 0 4px 10px rgba(0,0,0,0.2);
        }
        
        .conclusion-box {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 25px;
            border-radius: 15px;
            margin: 20px 0;
            text-align: center;
            font-size: 1.4em;
            font-weight: bold;
            box-shadow: 0 5px 15px rgba(0,0,0,0.3);
        }
        
        .conclusion-box.suitable {
            background: linear-gradient(135deg, #4CAF50 0%, #8BC34A 100%);
        }
        
        .conclusion-box.not-suitable {
            background: linear-gradient(135deg, #f44336 0%, #ff9800 100%);
        }
        
        .suitable {
            background: #4CAF50;
            color: white;
        }
        
        .not-suitable {
            background: #f44336;
            color: white;
        }
        
        .stats {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin: 20px 0;
        }
        
        .stat-item {
            background: #f8f9fa;
            padding: 15px;
            border-radius: 10px;
            text-align: center;
        }
        
        .stat-label {
            font-size: 0.9em;
            color: #666;
            margin-bottom: 5px;
        }
        
        .stat-value {
            font-size: 1.5em;
            font-weight: bold;
            color: #333;
        }
        
        .confidence-bar {
            background: #e0e0e0;
            border-radius: 10px;
            height: 30px;
            margin: 15px 0;
            overflow: hidden;
            position: relative;
        }
        
        .confidence-fill {
            height: 100%;
            background: linear-gradient(90deg, #4CAF50 0%, #8BC34A 100%);
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-weight: bold;
            transition: width 0.5s ease;
        }
        
        .confidence-fill.low {
            background: linear-gradient(90deg, #f44336 0%, #ff9800 100%);
        }
        
        .reason {
            background: #e3f2fd;
            padding: 15px;
            border-radius: 10px;
            margin-top: 15px;
            border-left: 4px solid #2196F3;
        }
        
        .reason-title {
            font-weight: bold;
            color: #1976D2;
            margin-bottom: 8px;
        }
        
        .keyword-analysis {
            margin-top: 15px;
            padding: 15px;
            background: #fff3e0;
            border-radius: 10px;
        }
        
        .keyword-title {
            font-weight: bold;
            color: #E65100;
            margin-bottom: 10px;
        }
        
        .keyword-stats {
            display: flex;
            gap: 20px;
            margin-top: 10px;
        }
        
        .error {
            background: #ffebee;
            color: #c62828;
            padding: 20px;
            border-radius: 10px;
            border-left: 4px solid #c62828;
        }
        
        @media (max-width: 768px) {
            h1 {
                font-size: 1.8em;
            }
            
            .work-header {
                flex-direction: column;
                align-items: flex-start;
                gap: 10px;
            }
            
            .stats {
                grid-template-columns: 1fr;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>📚 작품 사용자 적합성 분석 결과</h1>
"""
    
    for result in results_list:
        if 'error' in result:
            html += f"""
        <div class="work-card">
            <div class="error">
                <strong>오류:</strong> {result['error']}
            </div>
        </div>
"""
        else:
            suitable_class = 'suitable' if result['suitable'] else 'not-suitable'
            suitable_text = '✅ 입문자에게 적합함' if result['suitable'] else '❌ 입문자에게 부적합'
            confidence_class = 'low' if result['confidence'] < 60 else ''
            conclusion_message = f"이 작품은 입문자에게 <strong>적합합니다</strong> 👍" if result['suitable'] else f"이 작품은 입문자에게 <strong>부적합할 수 있습니다</strong> ⚠️"
            age_group = result.get('age_recommendation', {}).get('recommended_group', '성인')
            age_counts = result.get('age_recommendation', {}).get('counts', {})
            empathy = result.get('empathy', {})
            
            html += f"""
        <div class="work-card">
            <div class="work-header">
                <div class="work-name">{result['work_name']}</div>
                <div class="result-badge {suitable_class}">{suitable_text}</div>
            </div>
            
            <div class="conclusion-box {suitable_class}">
                {conclusion_message}
            </div>
            
            <div class="stat-item" style="margin: 10px 0; background:#eef7ff;">
                <div class="stat-label">연령대 추천</div>
                <div class="stat-value">{age_group}</div>
            </div>
            
            <div class="confidence-bar">
                <div class="confidence-fill {confidence_class}" style="width: {result['confidence']}%">
                    분석 신뢰도: {result['confidence']}%
                </div>
            </div>
            
            <div class="stats">
"""
            
            if result['avg_rating']:
                html += f"""
                <div class="stat-item">
                    <div class="stat-label">평균 평점</div>
                    <div class="stat-value">⭐ {result['avg_rating']}</div>
                </div>
"""
            
            html += f"""
                <div class="stat-item">
                    <div class="stat-label">총 리뷰 수</div>
                    <div class="stat-value">{result['total_reviews']}개</div>
                </div>
                
                <div class="stat-item">
                    <div class="stat-label">긍정 리뷰 비율</div>
                    <div class="stat-value">{result['positive_ratio']}%</div>
                </div>
                
                <div class="stat-item">
                    <div class="stat-label">종합 점수</div>
                    <div class="stat-value">{result['final_score']:.2f}</div>
                </div>
            </div>
            
            <div class="keyword-analysis">
                <div class="keyword-title">👥 연령대 언급 통계</div>
                <div class="keyword-stats">
                    <div>초등학생: {age_counts.get('초등학생', 0)}건</div>
                    <div>중학생: {age_counts.get('중학생', 0)}건</div>
                    <div>고등학생: {age_counts.get('고등학생', 0)}건</div>
                    <div>성인: {age_counts.get('성인', 0)}건</div>
                </div>
            </div>
"""
            
            if result['keyword_analysis']['positive_keywords_found'] > 0 or result['keyword_analysis']['negative_keywords_found'] > 0:
                html += f"""
            <div class="keyword-analysis">
                <div class="keyword-title">🔍 키워드 분석</div>
                <div class="keyword-stats">
                    <div>긍정 키워드: {result['keyword_analysis']['positive_keywords_found']}개</div>
                    <div>부정 키워드: {result['keyword_analysis']['negative_keywords_found']}개</div>
                    <div>감성 비율: {result['keyword_analysis']['sentiment_ratio']:.2f}</div>
                </div>
            </div>
"""

            html += f"""
        </div>
"""
    
    html += """
    </div>
</body>
</html>
"""
    
    return html


def analyze_all_and_generate_html() -> bool:
    """현재 폴더의 모든 CSV를 분석하고 HTML을 생성합니다. 변경이 있으면 True를 반환."""
    current_dir = Path('.')
    csv_files = [str(p) for p in current_dir.glob('*.csv')]

    if not csv_files:
        print("CSV 파일을 찾을 수 없습니다.")
        print("현재 디렉토리에 분석할 CSV 파일(작품명.csv)을 추가해주세요.")
        print("CSV 파일 형식: 리뷰내용,평점")
        return False

    print(f"{len(csv_files)}개의 CSV 파일을 찾았습니다.")
    print("각 작품의 사용자 적합성을 분석 중...")
    results = []

    for csv_file in csv_files:
        print(f"\n분석 중: {csv_file}")
        result = analyze_review_for_beginners(csv_file)
        results.append(result)
        if 'error' not in result:
            status_text = '적합' if result['suitable'] else '부적합'
            age_group = result.get('age_recommendation', {}).get('recommended_group', '성인')
            empathy = result.get('empathy', {})
            empathy_used = 'Y' if empathy.get('used') else 'N'
            avg_likes = empathy.get('avg_likes')
            avg_likes_text = f", 평균 공감: {avg_likes}" if avg_likes is not None else ""
            print(f"  결과: {status_text} (신뢰도: {result['confidence']}%), 연령대 추천: {age_group}, 공감가중 사용: {empathy_used}{avg_likes_text}")
        else:
            print(f"  오류: {result['error']}")

    html_content = generate_html(results)
    output_file = 'analysis_result.html'
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html_content)

    print(f"\n분석 완료! 결과가 '{output_file}' 파일로 저장되었습니다.")
    print(f"브라우저에서 '{output_file}' 파일을 열어서 결과를 확인하세요.")
    return True


def get_csv_state() -> dict:
    """CSV 파일들의 변경 감지를 위한 상태(수정시각, 크기)를 반환합니다."""
    state = {}
    for p in Path('.').glob('*.csv'):
        try:
            stat = p.stat()
            state[str(p)] = (stat.st_mtime, stat.st_size)
        except FileNotFoundError:
            continue
    return state


def main():
    """메인 함수: 단발 실행 또는 --watch 감시 모드"""
    parser = argparse.ArgumentParser(description="리뷰 CSV 분석 및 HTML 생성")
    parser.add_argument('--watch', action='store_true', help='CSV 변경 시 자동으로 재생성')
    parser.add_argument('--interval', type=float, default=2.0, help='감시 주기(초), 기본 2초')
    args = parser.parse_args()

    if not args.watch:
        analyze_all_and_generate_html()
        return

    print("감시 모드 시작: CSV 파일 변경 시 자동으로 HTML을 갱신합니다.")
    print("중지하려면 Ctrl+C 를 누르세요.")
    last_state = get_csv_state()
    # 시작 시 한 번 빌드
    analyze_all_and_generate_html()

    try:
        while True:
            time.sleep(args.interval)
            current_state = get_csv_state()
            if current_state != last_state:
                print("\n변경 감지됨. HTML을 다시 생성합니다...")
                analyze_all_and_generate_html()
                last_state = current_state
    except KeyboardInterrupt:
        print("\n감시 모드를 종료합니다.")


if __name__ == '__main__':
    main()

