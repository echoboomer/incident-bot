import React from 'react';
import { useSpring } from 'react-spring';

const useMove = ({
  x = 0,
  y = 0,
  rotation = 0,
  scale = 1,
  timing = 200,
  springConfig = {
    tension: 400,
    friction: 15
  }
}) => {
  const [isTouched, setIsTouched] = React.useState(false);
  const style = useSpring({
    display: 'inline-block',
    backfaceVisibility: 'hidden',
    transform: isTouched
      ? `translate(${x}px, ${y}px)
      rotate(${rotation}deg)
      scale(${scale})`
      : `translate(0px, 0px)
      rotate(0deg)
      scale(1)`,
    config: springConfig
  });

  React.useEffect(() => {
    if (!isTouched) {
      return;
    }

    const timeoutId = window.setTimeout(() => {
      setIsTouched(false);
    }, timing);

    return () => window.clearTimeout(timeoutId);
  }, [isTouched, timing]);

  const trigger = React.useCallback(() => setIsTouched(true), []);

  return [style, trigger];
};

export default useMove;
