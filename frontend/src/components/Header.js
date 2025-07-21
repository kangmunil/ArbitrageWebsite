import React from 'react';
import './Header.css'; // 새로운 CSS 파일 임포트 (나중에 생성)

function Header() {
  return (
    <header className="App-header">
      <div className="header-left">
        {/* 로고 이미지 또는 아이콘 */}
        <img src="/logo.svg" className="App-logo" alt="logo" /> {/* 예시 로고 경로 */}
        <h1>KimchiScan</h1>
      </div>
      <nav className="header-right">
        {/* "차트" 페이지로 이동할 수 있는 공간 */}
        <a href="#chart-section" className="nav-link">차트</a> {/* 임시 앵커 링크 */}
        {/* 다른 기능들을 위한 공간 */}
      </nav>
    </header>
  );
}

export default Header;