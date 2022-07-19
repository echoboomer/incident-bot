import React from 'react';
import { Card, CardActions, CardContent, CardHeader, IconButton } from '@mui/material';

import AnnouncementIcon from '@mui/icons-material/Announcement';
import ShareIcon from '@mui/icons-material/Share';
import MoreVertIcon from '@mui/icons-material/MoreVert';

import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend } from 'recharts';

export default function IncidentsChartCard(props) {
  let totals = {
    investigating: 0,
    identified: 0,
    monitoring: 0,
    resolved: 0
  };

  // Calculate Totals
  props.incidents.forEach((i) => {
    totals[i.status]++;
  });

  const data = [];

  for (const [key, value] of Object.entries(totals)) {
    data.push({
      name: key,
      incidents: value
    });
  }

  return (
    <Card raised style={{ display: 'flex', flexDirection: 'column' }}>
      <CardHeader
        avatar={<AnnouncementIcon />}
        action={
          <IconButton aria-label="settings">
            <MoreVertIcon />
          </IconButton>
        }
        title="Incidents Snapshot"
      />
      <CardContent>
        <BarChart
          width={500}
          height={300}
          data={data}
          margin={{
            left: 20
          }}>
          <CartesianGrid strokeDasharray="1 4" />
          <XAxis dataKey="name" />
          <YAxis />
          <Tooltip />
          <Legend />
          <Bar dataKey="incidents" fill="#8884d8" />
        </BarChart>
      </CardContent>
      <CardActions disableSpacing>
        <IconButton aria-label="share">
          <ShareIcon />
        </IconButton>
      </CardActions>
    </Card>
  );
}
