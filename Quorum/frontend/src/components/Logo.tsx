/**
 * Logo component - displays the Quorum brand with advanced visual effects
 * Features: animated gradients, glow effects, pulsing accent dot, and hover interactions
 */
import React from 'react';

interface LogoProps {
  size?: 'sm' | 'md' | 'lg';
  showTagline?: boolean;
  showAccent?: boolean;
}

export const Logo: React.FC<LogoProps> = ({ 
  size = 'md', 
  showTagline = true,
  showAccent = true
}) => {
  const sizeClasses = {
    sm: 'text-base',
    md: 'text-lg',
    lg: 'text-2xl'
  };

  const taglineSizeClasses = {
    sm: 'text-[9px] mt-1',
    md: 'text-[10px] mt-1.5',
    lg: 'text-xs mt-2'
  };

  const text = "Quorum";
  const splitIndex = Math.ceil(text.length / 2);
  
  return (
    <div className="logo-container group">
      {/* Animated glow background */}
      <div className="logo-glow" aria-hidden="true" />
      
      <h1 className={`logo-text ${sizeClasses[size]} animate-fade-in`}>
        <span className="logo-quorum animate-fade-in-up">
          <span className="logo-first-half">{text.slice(0, splitIndex)}</span>
          <span className="logo-second-half">{text.slice(splitIndex)}</span>
          {showAccent && <span className="logo-accent-dot" aria-hidden="true" />}
        </span>
      </h1>
      
      {showTagline && (
        <p className={`logo-tagline ${taglineSizeClasses[size]} animate-fade-in-up animate-stagger-2`}>
          Collaborative AI Reasoning
        </p>
      )}
    </div>
  );
};

