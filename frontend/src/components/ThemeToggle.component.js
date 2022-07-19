import React, { useEffect, useState } from 'react';
import { setTheme } from '../shared/setTheme';
import IconButton from '@mui/material/IconButton';
import DarkModeIcon from '@mui/icons-material/DarkMode';
import LightModeIcon from '@mui/icons-material/LightMode';

export function ThemeToggle() {
  const [togClass, setTogClass] = useState('dark');
  let theme = sessionStorage.getItem('theme');

  const handleOnClick = () => {
    if (sessionStorage.getItem('theme') === 'dark') {
      setTheme('light');
      setTogClass('light');
    } else {
      setTheme('dark');
      setTogClass('dark');
    }
    window.location.reload();
  };

  useEffect(() => {
    if (sessionStorage.getItem('theme') === 'dark') {
      setTogClass('dark');
    } else if (sessionStorage.getItem('theme') === 'light') {
      setTogClass('light');
    }
  }, [theme]);

  return (
    <div className="theme-toggle">
      <IconButton sx={{ ml: 1 }} onClick={handleOnClick} color="inherit">
        {togClass === 'dark' ? <LightModeIcon /> : <DarkModeIcon />}
      </IconButton>
    </div>
  );
}
