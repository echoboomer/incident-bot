import React, { Fragment, useEffect, useState } from 'react';
import axios from 'axios';
import {
  Alert,
  Button,
  Card,
  CardActions,
  CardContent,
  Container,
  Grid,
  IconButton,
  Snackbar,
  Typography
} from '@mui/material';
import Tooltip, { tooltipClasses } from '@mui/material/Tooltip';
import { styled } from '@mui/material/styles';
import IncidentsChartCard from './Incidents-chart.component';
import InfoIcon from '@mui/icons-material/Info';

import moment from 'moment';
import { apiUrl } from '../shared/Variables';

const HtmlTooltip = styled(({ className, ...props }) => (
  <Tooltip {...props} classes={{ popper: className }} />
))(({ theme }) => ({
  [`& .${tooltipClasses.tooltip}`]: {
    backgroundColor: '#f5f5f9',
    color: 'rgba(0, 0, 0, 0.87)',
    maxWidth: 220,
    fontSize: theme.typography.pxToRem(12),
    border: '1px solid #dadde9'
  }
}));

const Dashboard = () => {
  const [refreshData, setRefreshData] = useState(false);
  const [incidents, setIncidents] = useState([]);

  const [fetchIncidentsStatus, setFetchIncidentsStatus] = useState('');
  const [fetchIncidentsMessage, setFetchIncidentsMessage] = useState('');
  const [openFetchIncidentsStatus, setOpenFetchIncidentsStatus] = useState(false);

  function getAllIncidents() {
    var url = apiUrl + '/incidents';
    axios({
      method: 'GET',
      responseType: 'json',
      url: url
    })
      .then(function (response) {
        setIncidents(response.data.data);
      })
      .catch(function (error) {
        if (error.response) {
          setFetchIncidentsStatus('error');
          setFetchIncidentsMessage(
            `Error retrieving incidents from backend: ${error.response.data.error}`
          );
          setOpenFetchIncidentsStatus(true);
        } else if (error.request) {
          setFetchIncidentsStatus('error');
          setFetchIncidentsMessage(`Error retrieving incidents from backend: ${error}`);
          setOpenFetchIncidentsStatus(true);
        }
      });
  }

  // Retrieve incidents
  useEffect(() => {
    getAllIncidents();
  }, []);

  if (refreshData) {
    setRefreshData(false);
    getAllIncidents();
  }

  function daysOld(creationDate) {
    var dateCreated = new Date(moment(creationDate, 'YYYY-MM-DD HH:mm:ss'));
    var today = new Date();
    var diff = (today.getTime() - dateCreated.getTime()) / (1000 * 3600 * 24);

    return diff.toFixed();
  }

  //
  var agingIncidents = 0;
  incidents.forEach((i) => {
    if (daysOld(i.created_at) >= 7 && i.status != 'resolved') {
      agingIncidents += 1;
    }
  });

  //
  var openIncidents = 0;
  incidents.forEach((i) => {
    if (i.status != 'resolved') {
      openIncidents += 1;
    }
  });

  return (
    <div className="align-items-center justify-content-center" style={{ paddingTop: '2vh' }}>
      <Container>
        <Grid sx={{ flexGrow: 1 }} container columnSpacing={2} rowSpacing={4}>
          <Grid item xs={3}>
            <Card raised>
              <CardContent>
                <Typography gutterBottom variant="h5" component="div">
                  Total Incidents
                  <HtmlTooltip
                    title={
                      <Fragment>
                        <Typography color="inherit">What is this?</Typography>
                        <em>{'All incidents in the database.'}</em>
                      </Fragment>
                    }>
                    <IconButton>
                      <InfoIcon fontSize="small" color="info" sx={{ marginLeft: 2 }} />
                    </IconButton>
                  </HtmlTooltip>
                </Typography>
                <Typography variant="h2" color="text.secondary">
                  {incidents.length}
                </Typography>
              </CardContent>
              <CardActions>
                <Button size="small">Learn More</Button>
              </CardActions>
            </Card>
          </Grid>

          <Grid item xs={3}>
            <Card raised>
              <CardContent>
                <Typography gutterBottom variant="h5" component="div">
                  Open Incidents
                  <HtmlTooltip
                    title={
                      <Fragment>
                        <Typography color="inherit">What is this?</Typography>
                        <em>{'All incidents that are not resolved.'}</em>
                      </Fragment>
                    }>
                    <IconButton>
                      <InfoIcon fontSize="small" color="info" sx={{ marginLeft: 2 }} />
                    </IconButton>
                  </HtmlTooltip>
                </Typography>
                <Typography variant="h2" color="text.secondary">
                  {openIncidents}
                </Typography>
              </CardContent>
              <CardActions>
                <Button size="small">Learn More</Button>
              </CardActions>
            </Card>
          </Grid>

          <Grid item xs={3}>
            <Card raised sx={{ backgroundImage: 'linear-gradient(to right, #FADBD8, #F5B7B1)' }}>
              <CardContent>
                <Typography gutterBottom variant="h5" component="div">
                  Aging Incidents
                  <HtmlTooltip
                    title={
                      <Fragment>
                        <Typography color="inherit">What is this?</Typography>
                        <em>{'Incidents that are not resolved and 7+ days old.'}</em>
                      </Fragment>
                    }>
                    <IconButton>
                      <InfoIcon fontSize="small" color="info" sx={{ marginLeft: 2 }} />
                    </IconButton>
                  </HtmlTooltip>
                </Typography>
                <Typography variant="h2" color="error">
                  {agingIncidents}
                </Typography>
              </CardContent>
              <CardActions>
                <Button size="small">Learn More</Button>
              </CardActions>
            </Card>
          </Grid>

          <Grid item xs={6}>
            <Grid key="incidents-snapshot" item>
              <IncidentsChartCard incidents={incidents} />
            </Grid>
          </Grid>
        </Grid>
      </Container>
      {fetchIncidentsStatus && (
        <Container>
          <Snackbar
            open={openFetchIncidentsStatus}
            autoHideDuration={6000}
            anchorOrigin={{ vertical: 'top', horizontal: 'center' }}
            onClose={(event, reason) => {
              if (reason === 'clickaway') {
                return;
              }
              setOpenFetchIncidentsStatus(false);
            }}>
            <Alert
              severity={fetchIncidentsStatus ? fetchIncidentsStatus : 'info'}
              variant="filled"
              sx={{ width: '100%' }}>
              {fetchIncidentsMessage}
            </Alert>
          </Snackbar>
        </Container>
      )}
    </div>
  );
};

export default Dashboard;
