import React from 'react';

interface LoadingProps {
  message?: string;
  minHeight?: string;
}

const Loading: React.FC<LoadingProps> = ({ 
  message = "Loading...", 
  minHeight = "400px" 
}) => {
  return (
    <div 
      className="loading-container" 
      style={{ 
        display: 'flex', 
        flexDirection: 'column',
        alignItems: 'center', 
        justifyContent: 'center', 
        minHeight: minHeight,
        background: 'transparent',
        border: 'none',
        boxShadow: 'none',
        gap: '1rem'
      }}
    >
      <div className="loading-spinner"></div>
      <div className="loading-text">{message}</div>
    </div>
  );
};

export default Loading; 