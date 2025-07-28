import React, { useState, useEffect, useRef } from 'react';
import './PriceCell.css';

// Helper to format the price
const formatPrice = (price) => {
  if (price === null || price === undefined || isNaN(price)) {
    return '-';
  }
  const options = {
    maximumFractionDigits: price < 10 ? 4 : (price < 100 ? 2 : 0),
  };
  return price.toLocaleString('en-US', options);
};

const PriceCell = ({ price, currency }) => {
  // State to manage the animation CSS class
  const [animationClass, setAnimationClass] = useState('');
  // Ref to store the previous price to detect changes
  const prevPriceRef = useRef(price); // Initialize with current price

  useEffect(() => {
    console.log(`[PriceCell] ${currency} 가격 변화 감지: ${prevPriceRef.current} -> ${price}`); // 디버깅 로그 추가
    // Only run if price has actually changed
    if (price !== prevPriceRef.current) {
      // Determine animation direction
      const animation = price > prevPriceRef.current ? 'price-up' : 'price-down';
      setAnimationClass(animation);

      // After the animation duration, remove the class so it can be re-triggered
      const timer = setTimeout(() => {
        setAnimationClass('');
      }, 300); // This duration must match the CSS animation duration

      // Update the ref with the new price for the next render cycle
      prevPriceRef.current = price; // Update ref for next comparison

      // Cleanup timer on component unmount or if effect re-runs
      return () => clearTimeout(timer);
    }
  }, [price]); // Dependency on 'price' prop

  // Render the current 'price' prop directly, and apply animation class
  return (
    <td className={`price-cell ${animationClass}`}>
      <span className="currency">{currency}</span>
      {/* Step 8 (part 2): The new price is displayed on screen directly from the prop */}
      <span className="price">{formatPrice(price)}</span> {/* Directly use 'price' prop */}
    </td>
  );
};

// Removed React.memo temporarily for debugging, can add back later if it works
export default PriceCell;