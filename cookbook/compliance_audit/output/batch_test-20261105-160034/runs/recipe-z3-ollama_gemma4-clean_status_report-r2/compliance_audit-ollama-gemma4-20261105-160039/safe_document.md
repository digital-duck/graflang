WEEKLY PLATFORM STATUS, week 45 (internal, to be shared with the analytics vendor)

Availability
The Orion Gateway met its availability target this week: 99.95% against a target of 99.9%. There were two incidents.
INC-20431 (Tuesday, 14 minutes): a certificate on the staging load balancer expired; renewed the same day.
INC-20447 (Thursday, 6 minutes): a slow database failover; the replica was promoted automatically.

Capacity
Peak load was 4,820 requests per second on Wednesday at 15:10 UTC, about 62% of the tested ceiling. Storage use grew from
71% to 73%. The next capacity review is on 18 November.

Releases
Release 8.14.2 shipped on Monday. Release 8.15.0 is planned for 24 November and is waiting on two performance tests.

Notes for the vendor
Please focus the study on the failover time in INC-20447 and on whether the 62% peak leaves enough headroom.
