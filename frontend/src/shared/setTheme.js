import { createTheme } from '@mui/material/styles';

export function setTheme(themeName) {
  sessionStorage.setItem('theme', themeName);
  document.documentElement.className = themeName;
}

export let abGradientPerTheme, acGradientPerTheme, gradientBase;

export function keepTheme() {
  if (sessionStorage.getItem('theme')) {
    if (sessionStorage.getItem('theme') === 'dark') {
      setTheme('dark');
      abGradientPerTheme = `linear-gradient(to right, #1B4F72, #5DADE2)`;
      acGradientPerTheme = 'linear-gradient(to right, #808B96, #121212)';
      gradientBase = `#000000`;
    } else if (sessionStorage.getItem('theme') === 'light') {
      setTheme('light');
      abGradientPerTheme = `linear-gradient(to right, #01579B, #89CFF0)`;
      acGradientPerTheme = 'linear-gradient(to right, #ffffff, #0173cd)';
      gradientBase = `#ffffff`;
    }
  } else {
    setTheme('dark');
  }
}

export function setThemeParameters() {
  const darkTheme = createTheme({
    palette: {
      mode: 'dark'
    }
  });

  const lightTheme = createTheme({
    palette: {
      mode: 'light'
    }
  });

  if (sessionStorage.getItem('theme')) {
    if (sessionStorage.getItem('theme') === 'dark') {
      return darkTheme;
    } else if (sessionStorage.getItem('theme') === 'light') {
      return lightTheme;
    } else {
      return darkTheme;
    }
  }
}
