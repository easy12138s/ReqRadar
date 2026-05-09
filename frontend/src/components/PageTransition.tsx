import { motion } from 'framer-motion';
import type { ReactNode } from 'react';
import { useLocation } from 'react-router-dom';

interface PageTransitionProps {
  children: ReactNode;
}

export default function PageTransition({ children }: PageTransitionProps) {
  const location = useLocation();

  return (
    <motion.div
      key={location.pathname}
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -10 }}
      transition={{ 
        duration: 0.3, 
        ease: [0.25, 0.1, 0.25, 1], // 精细的缓动曲线，让动画更丝滑
      }}
      style={{ width: '100%', height: '100%' }}
    >
      {children}
    </motion.div>
  );
}
