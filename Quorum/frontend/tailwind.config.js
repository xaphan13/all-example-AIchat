/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Neutral scale - perceptually uniform grays
        neutral: {
          50: 'oklch(0.99 0.002 264)',      // Near white
          100: 'oklch(0.97 0.003 264)',     // Lightest gray
          200: 'oklch(0.93 0.005 264)',     // Light border
          300: 'oklch(0.87 0.007 264)',     // Border
          400: 'oklch(0.72 0.010 264)',     // Muted text
          500: 'oklch(0.58 0.012 264)',     // Secondary text
          600: 'oklch(0.45 0.012 264)',     // Body text
          700: 'oklch(0.35 0.012 264)',     // Emphasis text
          800: 'oklch(0.25 0.012 264)',     // Strong text
          900: 'oklch(0.18 0.010 264)',     // Headings
          950: 'oklch(0.12 0.008 264)',     // Maximum contrast
        },
        
        // Primary - balanced blue for actions and focus
        primary: {
          50: 'oklch(0.97 0.015 250)',      // Lightest tint
          100: 'oklch(0.94 0.025 250)',     // Very light
          200: 'oklch(0.88 0.045 250)',     // Light
          300: 'oklch(0.78 0.08 250)',      // Medium light
          400: 'oklch(0.68 0.12 250)',      // Medium
          500: 'oklch(0.58 0.15 250)',      // Base - primary action
          600: 'oklch(0.50 0.15 250)',      // Hover
          700: 'oklch(0.42 0.13 250)',      // Active
          800: 'oklch(0.35 0.10 250)',      // Dark
          900: 'oklch(0.28 0.08 250)',      // Darkest
        },
        
        // Accent - vibrant for highlights and CTAs
        accent: {
          50: 'oklch(0.97 0.020 290)',
          100: 'oklch(0.94 0.035 290)',
          200: 'oklch(0.88 0.065 290)',
          300: 'oklch(0.78 0.10 290)',
          400: 'oklch(0.68 0.14 290)',
          500: 'oklch(0.60 0.17 290)',      // Vibrant accent
          600: 'oklch(0.52 0.16 290)',
          700: 'oklch(0.44 0.14 290)',
          800: 'oklch(0.36 0.11 290)',
          900: 'oklch(0.28 0.08 290)',
        },
        
        // Success - natural green
        success: {
          50: 'oklch(0.97 0.015 155)',
          100: 'oklch(0.93 0.030 155)',
          200: 'oklch(0.87 0.055 155)',
          300: 'oklch(0.78 0.095 155)',
          400: 'oklch(0.68 0.13 155)',
          500: 'oklch(0.60 0.15 155)',      // Success indicator
          600: 'oklch(0.52 0.14 155)',
          700: 'oklch(0.44 0.12 155)',
          800: 'oklch(0.36 0.10 155)',
          900: 'oklch(0.28 0.08 155)',
        },
        
        // Warning - warm amber
        warning: {
          50: 'oklch(0.97 0.020 85)',
          100: 'oklch(0.93 0.040 85)',
          200: 'oklch(0.88 0.070 85)',
          300: 'oklch(0.80 0.11 85)',
          400: 'oklch(0.72 0.15 85)',
          500: 'oklch(0.68 0.17 85)',       // Warning indicator
          600: 'oklch(0.60 0.16 85)',
          700: 'oklch(0.52 0.14 85)',
          800: 'oklch(0.42 0.11 85)',
          900: 'oklch(0.32 0.08 85)',
        },
        
        // Error - clear red
        error: {
          50: 'oklch(0.97 0.015 25)',
          100: 'oklch(0.94 0.030 25)',
          200: 'oklch(0.88 0.055 25)',
          300: 'oklch(0.78 0.10 25)',
          400: 'oklch(0.68 0.15 25)',
          500: 'oklch(0.58 0.18 25)',       // Error indicator
          600: 'oklch(0.50 0.17 25)',
          700: 'oklch(0.42 0.15 25)',
          800: 'oklch(0.35 0.12 25)',
          900: 'oklch(0.28 0.09 25)',
        },
        
        // Info - cool cyan
        info: {
          50: 'oklch(0.97 0.015 220)',
          100: 'oklch(0.93 0.030 220)',
          200: 'oklch(0.87 0.055 220)',
          300: 'oklch(0.78 0.09 220)',
          400: 'oklch(0.68 0.12 220)',
          500: 'oklch(0.60 0.14 220)',      // Info indicator
          600: 'oklch(0.52 0.13 220)',
          700: 'oklch(0.44 0.11 220)',
          800: 'oklch(0.36 0.09 220)',
          900: 'oklch(0.28 0.07 220)',
        },
        
        // Surface colors for layering
        surface: {
          base: 'oklch(1 0 0)',             // Pure white
          elevated: 'oklch(0.99 0.001 264)', // Slightly off-white
          overlay: 'oklch(0.98 0.002 264)',  // Card backgrounds
          subtle: 'oklch(0.96 0.003 264)',   // Subtle backgrounds
        },
      },
      animation: {
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'fade-in': 'fadeIn 0.3s ease-in-out',
        'fade-in-up': 'fadeInUp 0.4s cubic-bezier(0.16, 1, 0.3, 1)',
        'fade-in-down': 'fadeInDown 0.4s cubic-bezier(0.16, 1, 0.3, 1)',
        'slide-up': 'slideUp 0.3s ease-out',
        'slide-in-right': 'slideInRight 0.35s cubic-bezier(0.16, 1, 0.3, 1)',
        'slide-in-left': 'slideInLeft 0.35s cubic-bezier(0.16, 1, 0.3, 1)',
        'scale-in': 'scaleIn 0.3s cubic-bezier(0.16, 1, 0.3, 1)',
        'shimmer': 'shimmer 2s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'bounce-subtle': 'bounceSubtle 0.6s ease-in-out',
        'shake': 'shake 0.4s cubic-bezier(0.36, 0.07, 0.19, 0.97)',
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        fadeInUp: {
          '0%': { 
            opacity: '0',
            transform: 'translateY(12px)'
          },
          '100%': { 
            opacity: '1',
            transform: 'translateY(0)'
          },
        },
        fadeInDown: {
          '0%': { 
            opacity: '0',
            transform: 'translateY(-12px)'
          },
          '100%': { 
            opacity: '1',
            transform: 'translateY(0)'
          },
        },
        slideUp: {
          '0%': { transform: 'translateY(10px)', opacity: '0' },
          '100%': { transform: 'translateY(0)', opacity: '1' },
        },
        slideInRight: {
          '0%': {
            opacity: '0',
            transform: 'translateX(-20px)'
          },
          '100%': {
            opacity: '1',
            transform: 'translateX(0)'
          },
        },
        slideInLeft: {
          '0%': {
            opacity: '0',
            transform: 'translateX(20px)'
          },
          '100%': {
            opacity: '1',
            transform: 'translateX(0)'
          },
        },
        scaleIn: {
          '0%': {
            opacity: '0',
            transform: 'scale(0.9)'
          },
          '100%': {
            opacity: '1',
            transform: 'scale(1)'
          },
        },
        shimmer: {
          '0%': {
            backgroundPosition: '-200% 0'
          },
          '100%': {
            backgroundPosition: '200% 0'
          },
        },
        bounceSubtle: {
          '0%, 100%': {
            transform: 'translateY(0)'
          },
          '50%': {
            transform: 'translateY(-4px)'
          },
        },
        shake: {
          '0%, 100%': {
            transform: 'translateX(0)'
          },
          '10%, 30%, 50%, 70%, 90%': {
            transform: 'translateX(-2px)'
          },
          '20%, 40%, 60%, 80%': {
            transform: 'translateX(2px)'
          },
        },
      },
      transitionTimingFunction: {
        'spring': 'cubic-bezier(0.16, 1, 0.3, 1)',
        'bounce-in': 'cubic-bezier(0.68, -0.55, 0.265, 1.55)',
      },
    },
  },
  plugins: [],
};

