import React from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter, Route, Routes } from 'react-router-dom';

import { ThemeProvider } from '@mui/material/styles';
import { keepTheme, setThemeParameters } from './shared/setTheme';

import App from './App';
import NotFoundPage from './components/404.component';
import Incidents from './incident/View';
import ViewSingleIncident from './incident/Single-incident';
import Jobs from './job/View';
import OnCall from './pager/View';
import Settings from './settings/View';
import PersistentDrawerLeft from './components/AppDrawer.component';

import 'bootstrap/dist/css/bootstrap.css';
import './App.css';

import reportWebVitals from './reportWebVitals';

const root = ReactDOM.createRoot(document.getElementById('root'));
keepTheme();
root.render(
  <React.StrictMode>
    <BrowserRouter basename="/app">
      <ThemeProvider theme={setThemeParameters()}>
        <PersistentDrawerLeft />
        <Routes>
          <Route path="/" element={<App />} />
          <Route path="/incidents" element={<Incidents />} />
          <Route path="/incidents/:incidentName" element={<ViewSingleIncident />} />
          <Route path="/on-call" element={<OnCall />} />
          <Route path="/jobs" element={<Jobs />} />
          <Route path="/settings" element={<Settings />} />
          <Route path="*" element={<NotFoundPage />} />
        </Routes>
      </ThemeProvider>
    </BrowserRouter>
  </React.StrictMode>
);

// If you want to start measuring performance in your app, pass a function
// to log results (for example: reportWebVitals(console.log))
// or send to an analytics endpoint. Learn more: https://bit.ly/CRA-vitals
reportWebVitals();
