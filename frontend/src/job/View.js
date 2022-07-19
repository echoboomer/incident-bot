import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { Container } from '@mui/material';

import { apiUrl } from '../shared/Variables';
import Table from './Table';

const Jobs = () => {
  const [refreshData, setRefreshData] = useState(false);
  const [jobs, setJobs] = useState([]);

  // Job functions
  function getAllJobs() {
    var url = apiUrl + '/jobs';
    axios({
      method: 'GET',
      responseType: 'json',
      url: url
    })
      .then(function (response) {
        setJobs(response.data);
      })
      .catch(function (error) {
        if (error.response) {
          console.log(error.response);
        } else if (error.request) {
          console.log(error.request);
        }
      });
  }

  // Retrieve jobs
  useEffect(() => {
    getAllJobs();
  }, []);

  if (refreshData) {
    setRefreshData(false);
    getAllJobs();
  }

  return (
    <div className="jobs-page" style={{ paddingTop: '5vh' }}>
      <Container maxWidth="" sx={{ width: '70%' }}>
        <Table jobs={jobs} setRefreshData={setRefreshData.bind()} />
      </Container>
    </div>
  );
};

export default Jobs;
