import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { Alert, Container, Snackbar } from '@mui/material';

import { apiUrl } from '../shared/Variables';

import Table from './Table';

const Incidents = () => {
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

  return (
    <div className="incidents-page">
      <Container maxWidth="" sx={{ width: '70%', paddingTop: '5vh' }}>
        <Table incidents={incidents} />
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

export default Incidents;
