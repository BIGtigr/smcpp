#ifndef DEMOGRAPHY_H
#define DEMOGRAPHY_H

template <typename T, size_t P>
class Demography
{
    public:
    virtual PiecewiseConstantRateFunction<T> distinguishedEta();
};

template <typename T>
class OnePopDemography : public Demography<T, 1>
{
    public:
    OnePopDemography(ParameterVector params, std::vector<double> hidden_states) : 
        eta(PiecewiseConstantRateFunction<T>(params, hidden_states)) {}

    PiecewiseConstantRateFunction<T> distinguishedEta()
    {
        return eta;
    }

    private:
    PiecewiseConstantRateFunction<T> eta;
};

template <typename T>
class TwoPopDemography : public Demography<T, 2>
{
    public:
    TwoPopDemography(ParameterVector params1, ParameterVector params2, double split_time) : 
        eta1(PiecewiseConstantRateFunction<T>(params1)),
        eta2(PiecewiseConstantRateFunction<T>(params2)),
        split(split) {}

    PiecewiseConstantRateFunction<T> distinguishedEta()
    {
        return eta1;
    }

    private:
    PiecewiseConstantRateFunction<T> eta1, eta2;
    double split;
};

#endif
