import React from 'react';
import { animated } from 'react-spring';
import useMove from './useMove';

const Move = ({ children, ...animationConfig }) => {
  const [style, trigger] = useMove(animationConfig);

  return (
    <animated.span style={style} onMouseEnter={trigger}>
      {children}
    </animated.span>
  );
};

export default Move;
