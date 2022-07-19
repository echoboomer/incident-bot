import React, { useEffect, useState } from 'react';
import axios from 'axios';

import {
  Box,
  CssBaseline,
  Divider,
  IconButton,
  List,
  ListItem,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Toolbar
} from '@mui/material';

import MuiDrawer from '@mui/material/Drawer';
import MuiAppBar from '@mui/material/AppBar';

import AddTaskIcon from '@mui/icons-material/AddTask';
import AnnouncementIcon from '@mui/icons-material/Announcement';
import ChevronLeftIcon from '@mui/icons-material/ChevronLeft';
import ChevronRightIcon from '@mui/icons-material/ChevronRight';
import DashboardIcon from '@mui/icons-material/Dashboard';
import GitHubIcon from '@mui/icons-material/GitHub';
import LogoutIcon from '@mui/icons-material/Logout';
import MenuIcon from '@mui/icons-material/Menu';
import PhoneAndroidIcon from '@mui/icons-material/PhoneAndroid';
import SettingsIcon from '@mui/icons-material/Settings';

import { styled, useTheme } from '@mui/material/styles';

import useToken from '../shared/useToken';
import { apiUrl } from '../shared/Variables';
import { ThemeToggle } from './ThemeToggle.component';
import ApplicationHeaderLogo from './Header-logo.component';
import { severities } from '../shared/Variables';
import IncidentCreateModal from './Create-incident-modal.component';

const drawerWidth = 240;

const openedMixin = (theme) => ({
  width: drawerWidth,
  transition: theme.transitions.create('width', {
    easing: theme.transitions.easing.sharp,
    duration: theme.transitions.duration.enteringScreen
  }),
  overflowX: 'hidden'
});

const closedMixin = (theme) => ({
  transition: theme.transitions.create('width', {
    easing: theme.transitions.easing.sharp,
    duration: theme.transitions.duration.leavingScreen
  }),
  overflowX: 'hidden',
  width: `calc(${theme.spacing(7)} + 1px)`,
  [theme.breakpoints.up('sm')]: {
    width: `calc(${theme.spacing(8)} + 1px)`
  }
});

const DrawerHeader = styled('div')(({ theme }) => ({
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'flex-end',
  padding: theme.spacing(0, 1),
  // necessary for content to be below app bar
  ...theme.mixins.toolbar
}));

const AppBar = styled(MuiAppBar, {
  shouldForwardProp: (prop) => prop !== 'open'
})(({ theme, open }) => ({
  zIndex: theme.zIndex.drawer + 1,
  transition: theme.transitions.create(['width', 'margin'], {
    easing: theme.transitions.easing.sharp,
    duration: theme.transitions.duration.leavingScreen
  }),
  ...(open && {
    marginLeft: drawerWidth,
    width: `calc(100% - ${drawerWidth}px)`,
    transition: theme.transitions.create(['width', 'margin'], {
      easing: theme.transitions.easing.sharp,
      duration: theme.transitions.duration.enteringScreen
    })
  })
}));

const Drawer = styled(MuiDrawer, { shouldForwardProp: (prop) => prop !== 'open' })(
  ({ theme, open }) => ({
    width: drawerWidth,
    flexShrink: 0,
    whiteSpace: 'nowrap',
    boxSizing: 'border-box',
    ...(open && {
      ...openedMixin(theme),
      '& .MuiDrawer-paper': openedMixin(theme)
    }),
    ...(!open && {
      ...closedMixin(theme),
      '& .MuiDrawer-paper': closedMixin(theme)
    })
  })
);

function logOut(removeToken) {
  var url = apiUrl + '/user/logout';
  axios({
    method: 'POST',
    url: url
  })
    .then(() => {
      removeToken();
      window.location.reload();
    })
    .catch((error) => {
      if (error.response) {
        console.log(error.response);
        console.log(error.response.status);
        console.log(error.response.headers);
      }
    });
}

export default function MiniDrawer() {
  const { removeToken } = useToken();
  const theme = useTheme();

  const drawerStateKey = 'drawerOpen';
  const defaultOpen = sessionStorage.getItem(drawerStateKey) === 'true';
  const [open, setOpen] = useState(defaultOpen);

  const handleDrawerOpen = () => {
    setOpen(true);
  };

  const handleDrawerClose = () => {
    setOpen(false);
  };

  useEffect(() => {
    sessionStorage.setItem(drawerStateKey, open);
  }, [open]);

  return (
    <>
      <Box sx={{ display: 'flex' }}>
        <CssBaseline />
        <AppBar position="fixed" open={open} color="primary">
          <Toolbar>
            <Box sx={{ display: 'flex', flexGrow: 1 }}>
              <IconButton
                color="inherit"
                aria-label="open drawer"
                onClick={handleDrawerOpen}
                edge="start"
                sx={{
                  marginRight: 5,
                  ...(open && { display: 'none' })
                }}>
                <MenuIcon />
              </IconButton>
              {!open && <ApplicationHeaderLogo />}
            </Box>
            <IncidentCreateModal apiUrl={apiUrl} severities={severities} />
          </Toolbar>
        </AppBar>
        <Drawer variant="permanent" open={open}>
          <Box sx={{ display: 'flex', flexDirection: 'column' }}>
            <DrawerHeader>
              <ApplicationHeaderLogo />
              <IconButton onClick={handleDrawerClose}>
                {theme.direction === 'rtl' ? <ChevronRightIcon /> : <ChevronLeftIcon />}
              </IconButton>
            </DrawerHeader>
            <Divider variant="middle" />
            <List>
              <Box sx={{ display: 'flex', flexDirection: 'column' }}>
                {/* Dashboard */}
                <ListItem key={`dashboard`} disablePadding sx={{ display: 'block' }}>
                  <ListItemButton key="dashboard" href="/app">
                    <ListItemIcon>
                      <DashboardIcon />
                    </ListItemIcon>
                    <ListItemText primary={`Dashboard`} />
                  </ListItemButton>
                </ListItem>

                {/* Incidents */}
                <ListItem key={`incidents`} disablePadding sx={{ display: 'block' }}>
                  <ListItemButton key="incidents" href="/app/incidents">
                    <ListItemIcon>
                      <AnnouncementIcon />
                    </ListItemIcon>
                    <ListItemText primary={`Incidents`} />
                  </ListItemButton>
                </ListItem>

                {/* Pager */}
                <ListItem key={`on-call`} disablePadding sx={{ display: 'block' }}>
                  <ListItemButton key="on-call" href="/app/on-call">
                    <ListItemIcon>
                      <PhoneAndroidIcon />
                    </ListItemIcon>
                    <ListItemText primary={`On-Call / Pager`} />
                  </ListItemButton>
                </ListItem>

                {/* Jobs */}
                <ListItem key={`jobs`} disablePadding sx={{ display: 'block' }}>
                  <ListItemButton key="jobs" href="/app/jobs">
                    <ListItemIcon>
                      <AddTaskIcon />
                    </ListItemIcon>
                    <ListItemText primary={`Jobs`} />
                  </ListItemButton>
                </ListItem>

                {/* Source */}
                <ListItem key={`source`} disablePadding sx={{ display: 'block' }}>
                  <ListItemButton
                    key="source"
                    href="https://github.com/echoboomer/incident-bot"
                    target="new">
                    <ListItemIcon>
                      <GitHubIcon />
                    </ListItemIcon>
                    <ListItemText primary={`Source`} />
                  </ListItemButton>
                </ListItem>

                <Divider />

                {/* Settings */}
                <ListItem key={`settings`} disablePadding sx={{ display: 'block' }}>
                  <ListItemButton key="settings" href="/app/settings">
                    <ListItemIcon>
                      <SettingsIcon />
                    </ListItemIcon>
                    <ListItemText primary={`Settings`} />
                  </ListItemButton>
                </ListItem>

                {/* Logout */}
                <ListItem key={`logout`} disablePadding sx={{ display: 'block' }}>
                  <ListItemButton key="logout" onClick={() => logOut(removeToken)}>
                    <ListItemIcon>
                      <LogoutIcon />
                    </ListItemIcon>
                    <ListItemText primary={`Log Out`} />
                  </ListItemButton>
                </ListItem>
              </Box>
              <Box
                sx={{ display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
                <ListItem key={`theme-toggle`} disablePadding sx={{ display: 'block' }}>
                  <ThemeToggle />
                </ListItem>
              </Box>
            </List>
          </Box>
        </Drawer>
      </Box>
    </>
  );
}
