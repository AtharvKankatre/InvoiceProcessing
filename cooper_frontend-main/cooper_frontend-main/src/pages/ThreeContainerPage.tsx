import React from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import './ThreeContainerPage.css';

const ThreeContainerPage: React.FC = () => {
  const navigate = useNavigate();

  const handleBackToDashboard = () => {
    navigate('/dashboard');
  };

  return (
    <div className="three-container-page">
      {/* First Container - 20% height */}
      <div className="container-top">
        <div className="container-content">
          <h1>Top Container (20% Height)</h1>
          <p>This container takes 20% of the viewport height</p>
          <div className="container-actions">
            <Button onClick={handleBackToDashboard} variant="outline">
              ← Back to Dashboard
            </Button>
            <span className="user-welcome">Welcome, User</span>
          </div>
        </div>
      </div>

      {/* Second Container - 10% height */}
      <div className="container-middle">
        <div className="container-content">
          <h2>Middle Container (10% Height)</h2>
          <p>This container takes 10% of the viewport height</p>
        </div>
      </div>

      {/* Third Container - Remaining 70% height */}
      <div className="container-bottom">
        <div className="container-content">
          <h2>Bottom Container (70% Height)</h2>
          <p>This container takes the remaining 70% of the viewport height</p>
          
          <div className="content-grid">
            <div className="content-card">
              <h3>Content Section 1</h3>
              <p>This is some sample content in the bottom container. You can add any content here like forms, tables, or other components.</p>
            </div>
            
            <div className="content-card">
              <h3>Content Section 2</h3>
              <p>Another content section with different information. This demonstrates how the layout works with multiple content areas.</p>
            </div>
            
            <div className="content-card">
              <h3>Content Section 3</h3>
              <p>Third content section showing the flexibility of this layout structure.</p>
            </div>
          </div>

          <div className="bottom-actions">
          </div>
        </div>
      </div>
    </div>
  );
};

export default ThreeContainerPage; 