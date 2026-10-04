# Exact finite-frame audit bounds

These proofs concern a fixed finite candidate frame and explicitly specified completion classes. They are not population or temporal generalization theorems. The formulas implement familiar extremal allocation reasoning; the contribution is their executable integration with distinct evidence contracts, not the invention of partial identification.

## Paired top-k difference with missing labels

Let A and B be two size-k top sets in a common finite frame F. Define c_i=1(i in A)-1(i in B). Then Delta=(sum_i c_i y_i)/k for binary labels y. Shared selected items and jointly unselected items have coefficient zero. Let O be known labels, b=sum_{i in O} c_i y_i, and n_+, n_-, n_0 be the unknown counts with coefficients +1,-1,0.

With unrestricted unknown binary labels the sharp bounds are (b-n_-)/k and (b+n_+)/k. To attain the lower bound, assign zero to unknown positive-coefficient items and one to unknown negative-coefficient items. Reverse those choices for the upper bound. Zero-coefficient labels do not affect the objective. Thus the paired difference is identified exactly when all nonzero-coefficient labels are known; if A=B it is zero even with no labels. This does not identify either absolute precision.

If an externally trusted total S of positives in F is available, let r=S-sum_{i in O} y_i, requiring 0<=r<=n_++n_-+n_0. The sharp bounds are

L=[b-min(r,n_-)+max(0,r-n_--n_0)]/k,
U=[b+min(r,n_+)-max(0,r-n_+-n_0)]/k.

For minimization allocate the remaining r positive labels to coefficient -1, then 0, then +1; maximization reverses that order. An exchange of a positive from a higher coefficient to a lower available one cannot increase the objective, proving optimality. These assignments witness attainability. A supplied total is an assumption, not something the optimizer authenticates.

## At most h label corrections

Suppose all observed labels y are known, but at most h may be flipped. Flipping i changes the numerator by d_i=c_i(1-2y_i), which belongs to {-1,0,1}. If q_- and q_+ count the -1 and +1 changes, respectively, the sharp interval is

[Delta_0-min(h,q_-)/k, Delta_0+min(h,q_+)/k].

Select the beneficial unit changes to attain either endpoint. Further flips cannot improve the corresponding endpoint. Because the budget is "at most", unused or zero-effect flips are unnecessary. This is a sensitivity class, not evidence that h real labels are erroneous or that the observed labels were blindly sealed.

## Missing candidates with bounded insertions

Assume the visible relative ranking order is fixed, at least k visible items exist, and at most r<=k hidden items may be inserted anywhere with arbitrary binary labels. Let p_j count positives among the first j visible items. If j hidden items enter the top k, the numerator is p_{k-j}+z for 0<=z<=j. The minimum over j<=r is p_{k-r}, since visible positive prefixes are nondecreasing. The maximum is p_{k-r}+r, since adding a hidden positive while displacing at most one visible positive cannot lower the maximum. Both are attainable by inserting r hidden items first, labelled all zero or all one. The sharp interval is [p_{k-r}/k,(p_{k-r}+r)/k].

Without a bound on hidden candidates, enough inserted all-zero or all-one candidates make absolute precision range from zero to one. The assumption that every insertion position is feasible is explicit; actual deterministic repository scores may constrain that class. The current convenience cohort establishes no hidden-candidate bound.

## Independent small oracle

`run_contract_audit.py` enumerates all binary completions for owned frames of size one through four, all relevant top sets, partial label maps, feasible trusted totals and correction budgets. Its oracle explicitly enumerates and filters completions rather than calling the extremal formulas. It also enumerates hidden-item locations and labels while preserving the visible order. The retained results comprise 6,150 missing-label checks, 14,146 fixed-total checks, 6,192 correction checks and 320 insertion checks: 26,808 exact comparisons. These checks corroborate the proofs on small universes; they are not a mechanized proof or 26,808 independent software workloads.
