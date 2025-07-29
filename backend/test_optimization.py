#!/usr/bin/env python3
"""
백엔드 최적화 테스트 스크립트

이 스크립트는 최적화된 백엔드 시스템의 성능을 테스트하고
기존 시스템과 비교 분석합니다.
"""

import asyncio
import time
import json
import logging
import sys
import statistics
from typing import Dict, List, Any
import websockets
import requests
import aiohttp

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class PerformanceTest:
    """백엔드 시스템의 성능을 테스트하기 위한 클래스입니다.

    WebSocket 연결, REST API 응답 시간, 시스템 통계 및 메모리 사용량을 측정합니다.

    Attributes:
        backend_url (str): 테스트할 백엔드 서버의 기본 URL.
        ws_url (str): 백엔드 WebSocket 서버의 URL.
        test_results (dict): 실행된 테스트의 결과를 저장하는 딕셔리.
    """
    
    def __init__(self, backend_url: str = "http://localhost:8000"):
        """PerformanceTest 클래스의 생성자입니다.

        Args:
            backend_url (str, optional): 테스트할 백엔드 서버의 URL. 기본값은 "http://localhost:8000"입니다.
        """
        self.backend_url = backend_url
        self.ws_url = backend_url.replace("http", "ws")
        self.test_results = {}
    
    async def test_websocket_connection(self, duration: int = 30) -> Dict[str, Any]:
        """지정된 시간 동안 WebSocket 연결을 테스트하고 성능 지표를 수집합니다.

        메시지 수신 빈도, 메시지 크기, 연결 지연 시간 등을 측정합니다.

        Args:
            duration (int, optional): WebSocket 연결을 테스트할 시간(초). 기본값은 30초입니다.

        Returns:
            Dict[str, Any]: 테스트 결과를 담은 딕셔너리.
                            포함되는 키: 'duration', 'messages_received', 'connection_attempts',
                            'connection_errors', 'messages_per_second', 'avg_message_size',
                            'avg_latency', 'max_latency', 'min_latency'.
        """
        logger.info(f"WebSocket 연결 테스트 시작 ({duration}초)")
        
        messages_received = 0
        connection_attempts = 0
        connection_errors = 0
        message_sizes = []
        latencies = []
        start_time = time.time()
        last_message_time = start_time
        
        try:
            connection_attempts += 1
            uri = f"{self.ws_url}/ws/prices"
            
            async with websockets.connect(uri) as websocket:
                logger.info("WebSocket 연결 성공")
                
                end_time = start_time + duration
                
                while time.time() < end_time:
                    try:
                        # 타임아웃을 짧게 설정하여 주기적으로 체크
                        message = await asyncio.wait_for(websocket.recv(), timeout=1.0)
                        
                        current_time = time.time()
                        latencies.append(current_time - last_message_time)
                        last_message_time = current_time
                        
                        # 메시지 크기 측정
                        message_size = len(message.encode('utf-8'))
                        message_sizes.append(message_size)
                        
                        # 메시지 파싱 테스트
                        try:
                            data = json.loads(message)
                            if isinstance(data, list):
                                messages_received += 1
                                
                                if messages_received % 10 == 0:
                                    logger.info(f"수신 메시지: {messages_received}개, 코인 수: {len(data)}")
                        except json.JSONDecodeError:
                            logger.warning("JSON 파싱 실패")
                            
                    except asyncio.TimeoutError:
                        # 타임아웃은 정상 (연결 확인용)
                        continue
                    except Exception as e:
                        logger.error(f"메시지 수신 오류: {e}")
                        break
                        
        except Exception as e:
            connection_errors += 1
            logger.error(f"WebSocket 연결 오류: {e}")
        
        total_time = time.time() - start_time
        
        return {
            "duration": total_time,
            "messages_received": messages_received,
            "connection_attempts": connection_attempts,
            "connection_errors": connection_errors,
            "messages_per_second": messages_received / total_time if total_time > 0 else 0,
            "avg_message_size": statistics.mean(message_sizes) if message_sizes else 0,
            "avg_latency": statistics.mean(latencies) if latencies else 0,
            "max_latency": max(latencies) if latencies else 0,
            "min_latency": min(latencies) if latencies else 0,
        }
    
    async def test_rest_api_performance(self, num_requests: int = 100) -> Dict[str, Any]:
        """지정된 횟수만큼 REST API 엔드포인트에 요청을 보내 성능을 테스트합니다.

        각 엔드포인트별로 성공률, 평균/최소/최대/중앙값 응답 시간을 측정합니다.

        Args:
            num_requests (int, optional): 각 엔드포인트에 보낼 요청의 수. 기본값은 100입니다.

        Returns:
            Dict[str, Any]: 각 엔드포인트별 테스트 결과를 담은 딕셔너리.
                            각 엔드포인트 결과는 'total_requests', 'successful_requests',
                            'failed_requests', 'success_rate', 'avg_response_time',
                            'min_response_time', 'max_response_time', 'median_response_time'를 포함합니다.
        """
        logger.info(f"REST API 성능 테스트 시작 ({num_requests}개 요청)")
        
        endpoints = [
            "/api/coin-names",
            "/api/fear_greed_index", 
            "/api/stats",
            "/api/liquidations/aggregated"
        ]
        
        results = {}
        
        for endpoint in endpoints:
            logger.info(f"테스트 중: {endpoint}")
            
            response_times = []
            success_count = 0
            error_count = 0
            
            async with aiohttp.ClientSession() as session:
                for i in range(num_requests):
                    start_time = time.time()
                    
                    try:
                        url = f"{self.backend_url}{endpoint}"
                        async with session.get(url, timeout=10) as response:
                            await response.json()
                            
                            response_time = time.time() - start_time
                            response_times.append(response_time)
                            
                            if response.status == 200:
                                success_count += 1
                            else:
                                error_count += 1
                                
                    except Exception as e:
                        error_count += 1
                        logger.warning(f"요청 실패: {e}")
                    
                    # 요청 간격 (너무 빠르게 보내지 않도록)
                    if i < num_requests - 1:
                        await asyncio.sleep(0.1)
            
            results[endpoint] = {
                "total_requests": num_requests,
                "successful_requests": success_count,
                "failed_requests": error_count,
                "success_rate": (success_count / num_requests) * 100,
                "avg_response_time": statistics.mean(response_times) if response_times else 0,
                "min_response_time": min(response_times) if response_times else 0,
                "max_response_time": max(response_times) if response_times else 0,
                "median_response_time": statistics.median(response_times) if response_times else 0,
            }
        
        return results
    
    async def test_system_stats(self) -> Dict[str, Any]:
        """백엔드 시스템의 현재 통계 데이터를 조회합니다.

        백엔드 API의 `/api/stats` 엔드포인트에 요청을 보내 시스템 통계 정보를 가져옵니다.

        Returns:
            Dict[str, Any]: 시스템 통계 데이터를 담은 딕셔너리.
                            요청 실패 시 'error' 키를 포함하는 딕셔너리를 반환합니다.
        """
        logger.info("시스템 통계 확인")
        
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.backend_url}/api/stats"
                async with session.get(url, timeout=10) as response:
                    if response.status == 200:
                        return await response.json()
                    else:
                        return {"error": f"HTTP {response.status}"}
        except Exception as e:
            return {"error": str(e)}
    
    async def test_memory_usage(self, duration: int = 60) -> Dict[str, Any]:
        """지정된 시간 동안 백엔드 시스템의 메모리 사용량을 모니터링합니다.

        주기적으로 시스템 통계를 조회하여 메모리 관련 지표를 기록합니다.

        Args:
            duration (int, optional): 메모리 사용량을 모니터링할 시간(초). 기본값은 60초입니다.

        Returns:
            Dict[str, Any]: 메모리 사용량 모니터링 결과를 담은 딕셔너리.
                            'duration', 'samples', 'history' 키를 포함합니다.
        """
        logger.info(f"메모리 사용량 모니터링 ({duration}초)")
        
        stats_history = []
        start_time = time.time()
        
        while time.time() - start_time < duration:
            try:
                stats = await self.test_system_stats()
                if "error" not in stats:
                    stats_history.append({
                        "timestamp": time.time(),
                        "stats": stats
                    })
                
                await asyncio.sleep(5)  # 5초마다 확인
                
            except Exception as e:
                logger.error(f"통계 수집 오류: {e}")
        
        return {
            "duration": duration,
            "samples": len(stats_history),
            "history": stats_history
        }
    
    def analyze_results(self) -> Dict[str, Any]:
        """수집된 테스트 결과를 분석하고 성능 요약 및 개선 권장 사항을 생성합니다.

        WebSocket 및 REST API 테스트 결과를 기반으로 전반적인 성능 점수를 계산합니다.

        Returns:
            Dict[str, Any]: 분석 결과를 담은 딕셔너리.
                            'summary', 'recommendations', 'performance_score' 키를 포함합니다.
        """
        logger.info("테스트 결과 분석 중...")
        
        analysis = {
            "summary": {},
            "recommendations": [],
            "performance_score": 0
        }
        
        # WebSocket 성능 분석
        if "websocket" in self.test_results:
            ws_result = self.test_results["websocket"]
            
            analysis["summary"]["websocket"] = {
                "status": "good" if ws_result["messages_per_second"] >= 1 else "poor",
                "messages_per_second": ws_result["messages_per_second"],
                "connection_success": ws_result["connection_errors"] == 0,
                "avg_latency_ms": ws_result["avg_latency"] * 1000
            }
            
            if ws_result["messages_per_second"] < 1:
                analysis["recommendations"].append("WebSocket 메시지 빈도가 낮습니다. 데이터 수집 최적화 필요")
            
            if ws_result["avg_latency"] > 2:
                analysis["recommendations"].append("WebSocket 지연시간이 높습니다. 네트워크 또는 처리 성능 확인 필요")
        
        # REST API 성능 분석
        if "rest_api" in self.test_results:
            api_results = self.test_results["rest_api"]
            
            total_success_rate = statistics.mean([
                result["success_rate"] for result in api_results.values()
            ])
            
            avg_response_time = statistics.mean([
                result["avg_response_time"] for result in api_results.values()
            ])
            
            analysis["summary"]["rest_api"] = {
                "overall_success_rate": total_success_rate,
                "avg_response_time_ms": avg_response_time * 1000,
                "status": "good" if total_success_rate >= 95 and avg_response_time < 1 else "poor"
            }
            
            if total_success_rate < 95:
                analysis["recommendations"].append("API 성공률이 낮습니다. 오류 처리 개선 필요")
            
            if avg_response_time > 1:
                analysis["recommendations"].append("API 응답 시간이 느립니다. 성능 최적화 필요")
        
        # 성능 점수 계산 (0-100)
        score = 100
        
        # WebSocket 점수
        if "websocket" in analysis["summary"]:
            ws_summary = analysis["summary"]["websocket"]
            if not ws_summary["connection_success"]:
                score -= 30
            if ws_summary["messages_per_second"] < 1:
                score -= 20
            if ws_summary["avg_latency_ms"] > 2000:
                score -= 15
        
        # REST API 점수
        if "rest_api" in analysis["summary"]:
            api_summary = analysis["summary"]["rest_api"]
            if api_summary["overall_success_rate"] < 95:
                score -= 20
            if api_summary["avg_response_time_ms"] > 1000:
                score -= 15
        
        analysis["performance_score"] = max(0, score)
        
        return analysis
    
    async def run_comprehensive_test(self) -> Dict[str, Any]:
        """백엔드 시스템에 대한 종합적인 성능 테스트를 실행합니다.

        WebSocket 연결 테스트, REST API 성능 테스트, 시스템 통계 확인,
        메모리 사용량 테스트를 순차적으로 수행하고, 그 결과를 분석합니다.

        Returns:
            Dict[str, Any]: 모든 테스트 결과와 분석을 포함하는 딕셔너리.
        """
        logger.info("=== 백엔드 최적화 종합 테스트 시작 ===")
        
        # 1. WebSocket 연결 테스트
        self.test_results["websocket"] = await self.test_websocket_connection(30)
        
        # 2. REST API 성능 테스트
        self.test_results["rest_api"] = await self.test_rest_api_performance(50)
        
        # 3. 시스템 통계 확인
        self.test_results["system_stats"] = await self.test_system_stats()
        
        # 4. 메모리 사용량 테스트
        self.test_results["memory_usage"] = await self.test_memory_usage(60)
        
        # 5. 결과 분석
        self.test_results["analysis"] = self.analyze_results()
        
        logger.info("=== 백엔드 최적화 종합 테스트 완료 ===")
        
        return self.test_results

def print_test_results(results: Dict[str, Any]):
    """성능 테스트 결과를 콘솔에 보기 좋게 출력합니다.

    성능 점수, WebSocket 테스트 결과, REST API 테스트 결과, 시스템 통계,
    그리고 개선 권장 사항을 포함하여 상세하게 출력합니다.

    Args:
        results (Dict[str, Any]): `run_comprehensive_test` 함수에서 반환된 테스트 결과 딕셔너리.
    """
    print("\n" + "="*60)
    print("백엔드 최적화 테스트 결과")
    print("="*60)
    
    # 성능 점수
    if "analysis" in results:
        analysis = results["analysis"]
        score = analysis["performance_score"]
        print(f"\n🎯 성능 점수: {score}/100")
        
        if score >= 80:
            print("✅ 우수한 성능")
        elif score >= 60:
            print("⚠️  양호한 성능")
        else:
            print("❌ 성능 개선 필요")
    
    # WebSocket 결과
    if "websocket" in results:
        ws = results["websocket"]
        print(f"\n📡 WebSocket 테스트:")
        print(f"   - 메시지 수신: {ws['messages_received']}개")
        print(f"   - 초당 메시지: {ws['messages_per_second']:.2f}개/초")
        print(f"   - 평균 지연시간: {ws['avg_latency']*1000:.1f}ms")
        print(f"   - 연결 오류: {ws['connection_errors']}회")
    
    # REST API 결과
    if "rest_api" in results:
        print(f"\n🌐 REST API 테스트:")
        for endpoint, result in results["rest_api"].items():
            print(f"   {endpoint}:")
            print(f"     - 성공률: {result['success_rate']:.1f}%")
            print(f"     - 평균 응답시간: {result['avg_response_time']*1000:.1f}ms")
    
    # 시스템 통계
    if "system_stats" in results and "error" not in results["system_stats"]:
        stats = results["system_stats"]
        print(f"\n📊 시스템 통계:")
        
        if "shared_data" in stats:
            shared = stats["shared_data"]
            print(f"   - Upbit 티커: {shared.get('upbit_tickers_count', 0)}개")
            print(f"   - Binance 티커: {shared.get('binance_tickers_count', 0)}개")
            print(f"   - 분당 업데이트: {shared.get('recent_updates_per_minute', 0)}회")
        
        if "websocket_manager" in stats:
            ws_mgr = stats["websocket_manager"]
            print(f"   - 활성 WebSocket 연결: {ws_mgr.get('active_connections', 0)}개")
            print(f"   - 전송된 메시지: {ws_mgr.get('messages_sent', 0)}개")
    
    # 권장사항
    if "analysis" in results and results["analysis"]["recommendations"]:
        print(f"\n💡 개선 권장사항:")
        for i, rec in enumerate(results["analysis"]["recommendations"], 1):
            print(f"   {i}. {rec}")
    
    print("\n" + "="*60)


async def main():
    """스크립트의 메인 실행 함수입니다.

    명령줄 인수를 통해 백엔드 URL을 받아 테스트를 실행하거나,
    기본값인 "http://localhost:8000"을 사용합니다.
    백엔드 서버의 가용성을 확인한 후, `PerformanceTest`를 초기화하고
    종합 테스트를 실행하며, 결과를 콘솔에 출력하고 JSON 파일로 저장합니다.
    """
    if len(sys.argv) > 1:
        backend_url = sys.argv[1]
    else:
        backend_url = "http://localhost:8000"
    
    print(f"테스트 대상: {backend_url}")
    
    # 백엔드 서버 가용성 확인
    try:
        response = requests.get(f"{backend_url}/", timeout=5)
        if response.status_code != 200:
            print(f"❌ 백엔드 서버 접근 불가: HTTP {response.status_code}")
            return
    except Exception as e:
        print(f"❌ 백엔드 서버 접근 불가: {e}")
        return
    
    print("✅ 백엔드 서버 확인 완료")
    
    # 성능 테스트 실행
    tester = PerformanceTest(backend_url)
    results = await tester.run_comprehensive_test()
    
    # 결과 출력
    print_test_results(results)
    
    # 결과를 JSON 파일로 저장
    with open("backend_performance_test_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False, default=str)
    
    print(f"\n📄 상세 결과가 'backend_performance_test_results.json'에 저장되었습니다.")

if __name__ == "__main__":
    asyncio.run(main())