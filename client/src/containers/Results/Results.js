import React, { Component } from "react"
import axios from "axios";

import classes from "./Results.module.css";
import Aux from "../../hoc/Aux";
import Modal from "../../components/UI/Modal/Modal";
import Spinner from "../../components/UI/Spinner/Spinner";
import {TableContainer} from "@material-ui/core";
import TablePagination from "@material-ui/core/TablePagination";
import Paper from "@material-ui/core/Paper";
import Table from "@material-ui/core/Table";
import TableBody from "@material-ui/core/TableBody";
import MatchList from "./MatchList/MatchList";
import Button from "@material-ui/core/Button";

class Results extends Component {

    state = {
        page: 0,
        rowsPerPage: 5,
        jobs: {},
        loading: false
    }

    componentDidMount() {
        this.setState({loading: true})
        axios({
             method: "get",
             url: process.env.REACT_APP_SERVER_ADDRESS + "/results/finished_jobs"
        }).then(res => {
            let jobs = {};
            res.data.forEach(jobId => jobs[jobId] = {rankedList: [], showRankedList: false});
            this.setState({loading: false, jobs: jobs});
        }).catch(err => {
            this.setState({loading: false});
            console.log(err);
        })
    }

    handleChangePage = (event, newPage) => {
        this.setState({page: newPage});
    };

    handleChangeRowsPerPage = (event) => {
        this.setState({rowsPerPage: +event.target.value});
        this.setState({page: 0});
    };

    deleteJob = (jobId) => {
        this.setState({loading: true});
        axios({
             method: "post",
             url: process.env.REACT_APP_SERVER_ADDRESS + "/results/delete_job/" + jobId
        }).then(() => {
            const jobs = {...this.state.jobs};
            delete jobs[jobId];
            this.setState({jobs: jobs, loading: false});
        }).catch(err => {
            this.setState({loading: false});
            console.log(err);
        })
    }

    toggleRankedList = (jobId) => {
        const jobs = {...this.state.jobs};
        const job = jobs[jobId];
        if(job.showRankedList){
            job.showRankedList = false;
            this.setState({jobs: jobs});
        }else if(job.rankedList.length !== 0){
            job.showRankedList = true;
            this.setState({jobs: jobs});
        }else{
            this.setState({loading: true});
            axios({
                 method: "get",
                 url: process.env.REACT_APP_SERVER_ADDRESS + "/results/job_results/" + jobId
            }).then(res => {
                job.showRankedList = true;
                job.rankedList = res.data;
                this.setState({loading: false, jobs: jobs});
            }).catch(err => {
                this.setState({loading: false});
                console.log(err);
            })
        }
    }

    render() {
        return (
            <Aux>
                <Modal show={this.state.loading}>
                    <Spinner />
                </Modal>
                <div className={classes.Parent}>
                    <Paper className={classes.Root}>
                        <TableContainer className={classes.Container}>
                            <Table className={classes.Results}>
                                <TableBody>
                                    {Object.keys(this.state.jobs).slice(this.state.page * this.state.rowsPerPage,
                                        this.state.page * this.state.rowsPerPage + this.state.rowsPerPage)
                                        .map((jobId) => {
                                            const job = this.state.jobs[jobId];
                                            const renderedList = job.showRankedList
                                                ? <MatchList key={jobId}
                                                           rankedList={job.rankedList}
                                                           jobId={jobId}/>
                                                           : null;
                                            const splitJobId = jobId.split("_");
                                            const id = splitJobId[0];
                                            const algorithmName = splitJobId[1];
                                            return (<div className={classes.Result}>
                                                        <p>Job: {id}</p>
                                                        <p>Algorithm: {algorithmName}</p>
                                                        <Button
                                                            variant="contained"
                                                            color="primary"
                                                            onClick={() => this.toggleRankedList(jobId)}>
                                                            Show/hide matches
                                                        </Button>
                                                        <Button
                                                            color="secondary"
                                                            onClick={() => this.deleteJob(jobId)}>
                                                            Delete job
                                                        </Button>
                                                        {renderedList}
                                                    </div>);
                                            }
                                        )
                                    }
                                </TableBody>
                            </Table>
                            <TablePagination
                                    rowsPerPageOptions={[5, 10, 25]}
                                    component="div"
                                    count={Object.keys(this.state.jobs).length}
                                    rowsPerPage={this.state.rowsPerPage}
                                    page={this.state.page}
                                    onChangePage={this.handleChangePage}
                                    onChangeRowsPerPage={this.handleChangeRowsPerPage}
                            />
                        </TableContainer>
                    </Paper>
                </div>
            </Aux>
        );
    }
}

export default Results;